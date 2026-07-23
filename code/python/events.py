"""R3 — Immutable structured event log for the SOR measurement instrument.

Every measurable moment of a run is appended as one JSON object per line to an
append-only ``output/sor-runs/<ts>/events.jsonl``. On close the file is SHA-256'd
and the digest is sealed into ``manifest.json`` (R2), so the event stream is
tamper-evident and reproducible: a replayed fixture circuit yields a
schema-valid log whose hash matches the manifest (instrument-validation gate
item 6).

Records carry only *metadata* — fingerprints, byte counts, latencies, decisions
— never message plaintext, keeping the zero-knowledge relay property intact. The
live emit points are wired by the R4 forwarder and R5 consent handlers; this
module is the logging primitive plus a deterministic fixture replay used by the
acceptance check. Replay spawns no engine and moves no traffic — it is pure
seeded event emission (containment-safe).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from cmd_chat.sor import config as sor_config
from cmd_chat.sor import provenance

# The closed vocabulary of loggable events (roadmap R3). Emitting anything else
# is a programming error and is refused.
EVENT_TYPES = frozenset(
    {
        "consent_request",
        "consent_accept",
        "consent_reject",
        "circuit_build",
        "hop_add",
        "bridge_forward",
        "churn_kill",
        "churn_spawn",
        "rebuild_start",
        "rebuild_done",
    }
)

# Every record carries exactly these keys (null where not applicable), so the
# JSONL is uniform and machine-checkable.
RECORD_KEYS = (
    "ts",
    "run_id",
    "event",
    "node_fp",
    "circuit_id",
    "hop_index",
    "bytes",
    "latency_ms",
    "decision",
    "seed",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def validate_record(rec: Dict[str, Any]) -> None:
    """Raise ValueError unless `rec` is a schema-valid event record."""

    def req(cond: bool, msg: str) -> None:
        if not cond:
            raise ValueError(f"event schema: {msg}")

    req(isinstance(rec, dict), "record must be an object")
    req(set(rec.keys()) == set(RECORD_KEYS), f"record keys must be exactly {RECORD_KEYS}")
    req(rec["event"] in EVENT_TYPES, f"unknown event {rec['event']!r}")
    req(isinstance(rec["ts"], str) and rec["ts"], "ts must be non-empty str")
    req(isinstance(rec["run_id"], str) and rec["run_id"], "run_id must be non-empty str")
    req(isinstance(rec["seed"], int) and 0 <= rec["seed"] <= (1 << 64) - 1, "seed u64")
    # Optional-but-typed fields.
    req(rec["node_fp"] is None or isinstance(rec["node_fp"], str), "node_fp str|null")
    req(rec["circuit_id"] is None or isinstance(rec["circuit_id"], str), "circuit_id str|null")
    req(rec["hop_index"] is None or isinstance(rec["hop_index"], int), "hop_index int|null")
    req(rec["bytes"] is None or (isinstance(rec["bytes"], int) and rec["bytes"] >= 0), "bytes>=0|null")
    req(
        rec["latency_ms"] is None or isinstance(rec["latency_ms"], (int, float)),
        "latency_ms number|null",
    )
    req(rec["decision"] is None or isinstance(rec["decision"], str), "decision str|null")


class EventLog:
    """Append-only JSONL writer. Never edits a byte already written; the only
    file operation is append. `close()` returns the SHA-256 of the whole file."""

    def __init__(self, run_dir: Path, run_id: str, seed: int) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / "events.jsonl"
        self.run_id = run_id
        self.seed = seed
        self._closed = False
        # Append mode: existing content is never truncated or rewritten.
        self._fh = self.path.open("a", encoding="utf-8")

    def emit(
        self,
        event: str,
        *,
        node_fp: Optional[str] = None,
        circuit_id: Optional[str] = None,
        hop_index: Optional[int] = None,
        bytes_: Optional[int] = None,
        latency_ms: Optional[float] = None,
        decision: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._closed:
            raise RuntimeError("event log is closed")
        rec = {
            "ts": _utc_now_iso(),
            "run_id": self.run_id,
            "event": event,
            "node_fp": node_fp,
            "circuit_id": circuit_id,
            "hop_index": hop_index,
            "bytes": bytes_,
            "latency_ms": latency_ms,
            "decision": decision,
            "seed": self.seed,
        }
        validate_record(rec)
        # Deterministic key order so the line bytes are stable.
        self._fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
        self._fh.flush()
        return rec

    def close(self) -> str:
        """Close the file and return its SHA-256 hex digest (over exact bytes)."""
        if not self._closed:
            self._fh.close()
            self._closed = True
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def __enter__(self) -> "EventLog":
        return self

    def __exit__(self, *exc: Any) -> None:
        if not self._closed:
            self._fh.close()
            self._closed = True


def replay_fixture_circuit(
    run_dir: Path,
    run_id: str,
    seed: int,
    pool: int = 5,
    hops: int = 3,
    rebuilds: int = 1,
) -> str:
    """Emit a deterministic fixture circuit's event stream from `seed` alone and
    return the SHA-256 of the closed log. Same seed -> identical circuit-build
    sequence (R1) -> identical event bodies (modulo wall-clock `ts`).

    Pure bookkeeping: no engine, no socket, no traffic. Used by the R3 acceptance
    check and instrument-validation gate item 6 (provenance integrity)."""
    circuits = sor_config.bringup(seed, pool, hops, rebuilds)
    log = EventLog(run_dir, run_id, seed)
    with log:
        for c_idx, hops_seq in enumerate(circuits):
            circuit_id = f"c{c_idx}"
            if c_idx > 0:
                log.emit("rebuild_start", circuit_id=circuit_id)
            # Consent handshake per hop, then build.
            for h_idx, node in enumerate(hops_seq):
                node_fp = f"{node:08x}"
                log.emit("consent_request", node_fp=node_fp, circuit_id=circuit_id, hop_index=h_idx)
                log.emit(
                    "consent_accept",
                    node_fp=node_fp,
                    circuit_id=circuit_id,
                    hop_index=h_idx,
                    decision="accept",
                )
            log.emit("circuit_build", circuit_id=circuit_id, hop_index=len(hops_seq))
            for h_idx, node in enumerate(hops_seq):
                log.emit(
                    "hop_add",
                    node_fp=f"{node:08x}",
                    circuit_id=circuit_id,
                    hop_index=h_idx,
                    bytes_=1024,
                    latency_ms=1.0 + h_idx,
                )
            if c_idx > 0:
                log.emit("rebuild_done", circuit_id=circuit_id)
    return log.close()


def replay_and_seal(
    run_dir: Path,
    manifest: provenance.RunManifest,
    pool: int = 5,
    hops: int = 3,
    rebuilds: int = 1,
) -> Dict[str, Any]:
    """End-to-end fixture: write the R2 manifest, replay the fixture event
    stream, seal its SHA-256 into the manifest, and return the sealed manifest.
    This is exactly the gate item 6 flow (schema-valid events + hash match)."""
    provenance.write_manifest(run_dir, manifest)
    sha = replay_fixture_circuit(run_dir, manifest.run_id, manifest.sor_seed, pool, hops, rebuilds)
    return provenance.seal_manifest(run_dir, sha)
