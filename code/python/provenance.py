"""R2 — Run manifest / provenance writer for the SOR measurement instrument.

`write_manifest()` freezes, at circuit-experiment start, everything needed to
reproduce and audit a run: the R1 `--sor-seed`, the topology / selector / churn
schedule id, one persona fingerprint per participating node (mirrors
`hh/src/persona.rs::fingerprint_of`), the worktree git SHA, the isolated engine
kind + image digest, a pip/cargo dependency freeze, and start/stop timestamps.
It writes an immutable `output/sor-runs/<ts>/manifest.json`.

Provenance only — this module forwards no traffic and spawns no engine. As
defense-in-depth it refuses to record a non-isolated (`local`) engine, but the
load-bearing containment assertion lives with the R4 forwarder. The event-log
SHA-256 field is reserved here and filled by R3 when the log is closed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "sor-manifest/1"

# Engines that satisfy the containment law (isolated-engine-only). "local" is
# never a valid engine for a SOR run — recording it is refused.
ISOLATED_ENGINES = ("docker", "multipass")


def node_fingerprint(pub_b64: str) -> str:
    """Short fingerprint of a base64 Ed25519 pubkey: sha256(raw)[:4] hex.

    Bit-for-bit mirror of hh/src/persona.rs::fingerprint_of. Raises ValueError
    on undecodable input (a node with no valid persona cannot be recorded)."""
    try:
        raw = base64.b64decode(pub_b64, validate=True)
    except Exception as exc:  # noqa: BLE001 - normalize to ValueError
        raise ValueError(f"invalid persona pubkey: {exc}") from exc
    return hashlib.sha256(raw).digest()[:4].hex()


@dataclass
class Node:
    """A participating node in a SOR circuit run."""

    role: str  # "host" | "hop" | "bridge"
    persona_pub_b64: str
    engine: str = "docker"
    image_digest: Optional[str] = None

    def to_entry(self) -> Dict[str, Any]:
        if self.engine not in ISOLATED_ENGINES:
            raise ValueError(
                f"containment: node engine {self.engine!r} is not isolated "
                f"(allowed: {ISOLATED_ENGINES})"
            )
        return {
            "role": self.role,
            "persona_pub_b64": self.persona_pub_b64,
            "fingerprint": node_fingerprint(self.persona_pub_b64),
            "engine": self.engine,
            "image_digest": self.image_digest,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def capture_git(worktree_root: Path) -> Dict[str, Any]:
    """Best-effort worktree git provenance. Never raises; records nulls if the
    worktree is not a git repo (a manifest must still be schema-valid)."""

    def _run(args: List[str]) -> Optional[str]:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=str(worktree_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return out.stdout.strip() if out.returncode == 0 else None
        except Exception:  # noqa: BLE001
            return None

    sha = _run(["rev-parse", "HEAD"])
    branch = _run(["rev-parse", "--abbrev-ref", "HEAD"])
    status = _run(["status", "--porcelain"])
    return {
        "worktree_sha": sha,
        "branch": branch,
        "dirty": bool(status) if status is not None else None,
    }


def capture_deps(worktree_root: Path) -> Dict[str, Any]:
    """Freeze dependency provenance: sha256 of the pip freeze list and of the
    Cargo.lock (if present). Records the freeze list itself for auditability."""
    try:
        freeze = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout
    except Exception:  # noqa: BLE001
        freeze = ""
    pip_lines = sorted(l for l in freeze.splitlines() if l.strip())
    pip_blob = "\n".join(pip_lines).encode()

    cargo_lock = worktree_root / "hh" / "Cargo.lock"
    cargo_sha: Optional[str] = None
    if cargo_lock.is_file():
        cargo_sha = hashlib.sha256(cargo_lock.read_bytes()).hexdigest()

    return {
        "pip_freeze_sha256": hashlib.sha256(pip_blob).hexdigest(),
        "pip_freeze": pip_lines,
        "cargo_lock_sha256": cargo_sha,
    }


@dataclass
class RunManifest:
    """In-memory manifest; `write()` renders it immutably to disk."""

    run_id: str
    sor_seed: int
    topology: str
    selector: str
    churn_schedule_id: str
    nodes: List[Node]
    engine_kind: str = "docker"
    engine_image_digest: Optional[str] = None
    worktree_root: Path = field(default_factory=lambda: Path.cwd())
    start_utc: Optional[str] = None
    stop_utc: Optional[str] = None
    # R7 agent arm: model id + weights digest of the selector backend (e.g. the
    # local Ollama model), so an agent-selected run pins the exact model it used.
    selector_backend: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        if self.engine_kind not in ISOLATED_ENGINES:
            raise ValueError(
                f"containment: run engine {self.engine_kind!r} is not isolated "
                f"(allowed: {ISOLATED_ENGINES})"
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "created_utc": _utc_now_iso(),
            "sor_seed": self.sor_seed,
            "topology": self.topology,
            "selector": self.selector,
            "churn_schedule_id": self.churn_schedule_id,
            "nodes": [n.to_entry() for n in self.nodes],
            "engine": {
                "kind": self.engine_kind,
                "image_digest": self.engine_image_digest,
            },
            "selector_backend": self.selector_backend,
            "git": capture_git(self.worktree_root),
            "deps": capture_deps(self.worktree_root),
            "timestamps": {
                "start_utc": self.start_utc or _utc_now_iso(),
                "stop_utc": self.stop_utc,
            },
            # Reserved for R3: sha256 of the closed events.jsonl.
            "events": {"path": "events.jsonl", "sha256": None},
        }


def seal_manifest(
    run_dir: Path, events_sha256: str, stop_utc: Optional[str] = None
) -> Dict[str, Any]:
    """R3 close step: seal the closed events.jsonl SHA-256 (and stop timestamp)
    into an existing manifest.json exactly once.

    This is the one sanctioned mutation of a manifest — a single None -> hash
    transition completing the document. Re-sealing an already-sealed manifest is
    refused, preserving artifact immutability."""
    run_dir = Path(run_dir)
    path = run_dir / "manifest.json"
    doc = json.loads(path.read_text())
    if doc.get("events", {}).get("sha256") is not None:
        raise ValueError("events already sealed (manifest is immutable)")
    doc["events"]["sha256"] = events_sha256
    doc["timestamps"]["stop_utc"] = stop_utc or _utc_now_iso()
    validate_manifest(doc)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return doc


def write_manifest(run_dir: Path, manifest: RunManifest) -> Dict[str, Any]:
    """Render `manifest` to `<run_dir>/manifest.json` and return the dict.

    Refuses to overwrite an existing manifest (artifacts are immutable). The
    written document is validated before return; an invalid manifest raises and
    leaves nothing partial on disk."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "manifest.json"
    if path.exists():
        raise FileExistsError(f"manifest already exists (immutable): {path}")

    doc = manifest.to_dict()
    validate_manifest(doc)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return doc


# --- schema -----------------------------------------------------------------

def validate_manifest(doc: Dict[str, Any]) -> None:
    """Explicit, dependency-free schema check. Raises ValueError on any
    violation. This IS the R2 acceptance predicate (schema-valid + non-empty
    seed + >=1 fingerprint per participating node)."""

    def req(cond: bool, msg: str) -> None:
        if not cond:
            raise ValueError(f"manifest schema: {msg}")

    req(isinstance(doc, dict), "root must be an object")
    req(doc.get("schema_version") == SCHEMA_VERSION, "wrong/missing schema_version")
    for key in (
        "run_id",
        "created_utc",
        "sor_seed",
        "topology",
        "selector",
        "churn_schedule_id",
        "nodes",
        "engine",
        "git",
        "deps",
        "timestamps",
        "events",
    ):
        req(key in doc, f"missing top-level key {key!r}")

    req(isinstance(doc["run_id"], str) and doc["run_id"], "run_id must be non-empty str")
    req(isinstance(doc["sor_seed"], int), "sor_seed must be an int")
    req(0 <= doc["sor_seed"] <= (1 << 64) - 1, "sor_seed out of u64 range")

    for f in ("topology", "selector", "churn_schedule_id"):
        req(isinstance(doc[f], str) and doc[f], f"{f} must be non-empty str")

    nodes = doc["nodes"]
    req(isinstance(nodes, list) and len(nodes) >= 1, "nodes must be a non-empty list")
    for i, n in enumerate(nodes):
        req(isinstance(n, dict), f"node[{i}] must be an object")
        req(isinstance(n.get("role"), str) and n["role"], f"node[{i}].role required")
        fp = n.get("fingerprint")
        req(
            isinstance(fp, str) and len(fp) == 8 and all(c in "0123456789abcdef" for c in fp),
            f"node[{i}] must carry a persona fingerprint (8 hex chars)",
        )
        eng = n.get("engine")
        req(eng in ISOLATED_ENGINES, f"node[{i}].engine {eng!r} not isolated (containment)")

    engine = doc["engine"]
    req(isinstance(engine, dict), "engine must be an object")
    req(engine.get("kind") in ISOLATED_ENGINES, "engine.kind not isolated (containment)")

    ts = doc["timestamps"]
    req(isinstance(ts, dict) and isinstance(ts.get("start_utc"), str) and ts["start_utc"],
        "timestamps.start_utc required")

    ev = doc["events"]
    req(isinstance(ev, dict) and "sha256" in ev and "path" in ev, "events block malformed")
