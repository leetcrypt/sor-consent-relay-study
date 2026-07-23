"""Instrument-validation gate re-confirmation (prereg §5) for the RQ1+RQ2 path.

Re-runs the six boolean gate items and writes an auditable ``gate-report.json``.
This is calibration/validation on **fixtures only** — it collects no
confirmatory-cell data, so it is legitimate start-line work under the freeze:

  1. 3-hop e2e delivery + per-hop pcap checksums (R4, live isolated docker);
  2. seeded reproducibility — same seed → identical circuit-build sequence (R1);
  3. correlator calibration — known-linked AUC≈1, known-unlinked AUC≈0.5 (R7);
  4. entropy estimator returns H = log2(N) for N equiprobable senders (R7);
  5. forwarders isolated-engine-only — ``assert engine != local`` or refuse (R4);
  6. provenance integrity — replayed fixture events SHA-256 matches the sealed
     manifest; append-only (R2/R3).

Item 1 stands up isolated **docker** containers and moves only self-generated
fixture bytes between our own containers (containment-safe, always torn down).
Items 2-6 are pure offline checks. Nothing here forwards real/third-party
traffic, touches an external target, or runs a forwarder on the host.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cmd_chat.sor import events as sor_events
from cmd_chat.sor import forwarder as sor_forwarder
from cmd_chat.sor.analysis.detectors import (
    bridge_correlation_auc,
    shannon_entropy_bits,
    synthetic_bridge_fixture,
)
from cmd_chat.sor.config import bringup
from cmd_chat.sor.provenance import Node, RunManifest, validate_manifest

# Calibration tolerances (fixtures, ground truth known by construction).
_AUC_LINKED_MIN = 0.99      # known-linked control must separate near-perfectly.
_AUC_UNLINKED_TOL = 0.05    # known-unlinked mean must sit within 0.05 of chance.
_ENTROPY_TOL = 1e-9         # H = log2(N) must hold to floating-point exactness.
_UNLINKED_SEEDS = 40        # seeds averaged for the unlinked-chance calibration.


@dataclass
class GateItem:
    """One §5 gate item's re-confirmation outcome."""

    n: int
    name: str
    passed: bool
    status: str               # "green" | "red" | "unavailable"
    evidence: Dict[str, Any] = field(default_factory=dict)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fixture_pubkey(seed: int, role: str) -> str:
    raw = hashlib.sha256(f"sor-gate|{seed}|{role}".encode()).digest()  # 32 bytes
    import base64

    return base64.b64encode(raw).decode()


# --------------------------------------------------------------------------- #
# Item 1 — live 3-hop e2e delivery (isolated docker).
# --------------------------------------------------------------------------- #
def _item1_e2e(out_root: Path, seed: int, *, allow_live: bool) -> GateItem:
    """Stand up a 3-hop nested-SSH docker circuit, deliver a seed-deterministic
    self-payload end-to-end, and require per-hop pcap checksums. Marked
    ``unavailable`` (not ``red``) when the docker engine/image is absent — a
    missing execution boundary is not a failed instrument."""
    have_docker = shutil.which("docker") is not None
    if not (allow_live and have_docker):
        return GateItem(1, "3-hop e2e delivery + pcap checksums", False, "unavailable",
                        {"reason": "docker engine/image not available or live run disabled",
                         "have_docker": have_docker})
    try:
        res = sor_forwarder.run_circuit_fixture(seed, engine="docker", hops=3,
                                                out_root=out_root)
    except Exception as exc:  # noqa: BLE001 - report, never crash the gate
        return GateItem(1, "3-hop e2e delivery + pcap checksums", False, "red",
                        {"error": f"{type(exc).__name__}: {exc}"})
    pcaps_ok = len(res.pcap_sha256) == 3 and all(res.pcap_sha256.values())
    passed = bool(res.delivered and pcaps_ok
                  and res.received_sha256 == res.payload_sha256)
    return GateItem(1, "3-hop e2e delivery + pcap checksums", passed,
                    "green" if passed else "red",
                    {"run_id": res.run_id, "delivered": res.delivered,
                     "payload_sha256": res.payload_sha256,
                     "received_sha256": res.received_sha256,
                     "pcap_sha256": {str(k): v for k, v in res.pcap_sha256.items()},
                     "events_sha256": res.events_sha256})


# --------------------------------------------------------------------------- #
# Item 2 — seeded reproducibility (R1).
# --------------------------------------------------------------------------- #
def _item2_reproducible(*, pool: int = 5, hops: int = 3, rebuilds: int = 3) -> GateItem:
    seed = 0xC0FFEE
    a = bringup(seed, pool, hops, rebuilds)
    b = bringup(seed, pool, hops, rebuilds)
    other = bringup(seed ^ 0x1, pool, hops, rebuilds)
    passed = a == b and a != other
    return GateItem(2, "seeded circuit-build reproducibility", passed,
                    "green" if passed else "red",
                    {"seed": seed, "identical_on_replay": a == b,
                     "differs_on_other_seed": a != other, "sequence": a})


# --------------------------------------------------------------------------- #
# Item 3 — correlator calibration (R7).
# --------------------------------------------------------------------------- #
def _item3_correlator() -> GateItem:
    linked_aucs = [bridge_correlation_auc(*synthetic_bridge_fixture(s, linked=True))
                   for s in range(_UNLINKED_SEEDS)]
    unlinked_aucs = [bridge_correlation_auc(*synthetic_bridge_fixture(s, linked=False))
                     for s in range(_UNLINKED_SEEDS)]
    linked_min = min(linked_aucs)
    unlinked_mean = sum(unlinked_aucs) / len(unlinked_aucs)
    passed = linked_min >= _AUC_LINKED_MIN and abs(unlinked_mean - 0.5) <= _AUC_UNLINKED_TOL
    return GateItem(3, "correlator calibration (linked≈1 / unlinked≈0.5)", passed,
                    "green" if passed else "red",
                    {"linked_auc_min": linked_min, "unlinked_auc_mean": unlinked_mean,
                     "n_seeds": _UNLINKED_SEEDS, "linked_floor": _AUC_LINKED_MIN,
                     "unlinked_tol": _AUC_UNLINKED_TOL})


# --------------------------------------------------------------------------- #
# Item 4 — entropy estimator H = log2(N) (R7).
# --------------------------------------------------------------------------- #
def _item4_entropy() -> GateItem:
    checks = []
    ok = True
    for n in (2, 4, 8, 16, 64):
        h = shannon_entropy_bits([1] * n)  # N equiprobable senders
        exact = abs(h - math.log2(n)) <= _ENTROPY_TOL
        ok = ok and exact
        checks.append({"N": n, "H": h, "log2N": math.log2(n), "exact": exact})
    return GateItem(4, "entropy estimator H = log2(N)", ok,
                    "green" if ok else "red", {"checks": checks, "tol": _ENTROPY_TOL})


# --------------------------------------------------------------------------- #
# Item 5 — isolated-engine assertion (R4).
# --------------------------------------------------------------------------- #
def _item5_isolation() -> GateItem:
    refused_local = False
    refused_unknown = False
    accepts_docker = False
    try:
        sor_forwarder.assert_isolated("local")
    except sor_forwarder.ContainmentError:
        refused_local = True
    try:
        sor_forwarder.assert_isolated("host-native")
    except sor_forwarder.ContainmentError:
        refused_unknown = True
    try:
        sor_forwarder.assert_isolated("docker")
        accepts_docker = True
    except sor_forwarder.ContainmentError:
        accepts_docker = False
    passed = refused_local and refused_unknown and accepts_docker
    return GateItem(5, "forwarders isolated-engine-only (assert engine != local)", passed,
                    "green" if passed else "red",
                    {"refused_local": refused_local, "refused_unknown": refused_unknown,
                     "accepts_docker": accepts_docker})


# --------------------------------------------------------------------------- #
# Item 6 — provenance integrity (R2/R3).
# --------------------------------------------------------------------------- #
def _item6_provenance(out_root: Path, *, pool: int = 5, hops: int = 3) -> GateItem:
    seed = 0x5EED
    # Unique run subdir per invocation so each produces fresh write-once artifacts
    # (and run_gate stays safely repeatable into a reused out_dir).
    run_id = f"gate6-{seed:016x}-{uuid.uuid4().hex[:8]}"
    run_dir = Path(out_root) / run_id
    nodes = [Node(role=r, persona_pub_b64=_fixture_pubkey(seed, r), engine="docker")
             for r in ("host", "hop", "hop")]
    manifest = RunManifest(run_id=run_id, sor_seed=seed, topology="1house",
                           selector="static", churn_schedule_id="none", nodes=nodes,
                           engine_kind="docker", worktree_root=Path.cwd())
    sealed = sor_events.replay_and_seal(run_dir, manifest, pool=pool, hops=hops, rebuilds=1)
    validate_manifest(sealed)  # raises on any schema violation
    recomputed = hashlib.sha256((run_dir / "events.jsonl").read_bytes()).hexdigest()
    sha_match = sealed["events"]["sha256"] == recomputed

    # Append-only / immutability: re-sealing the same manifest is refused.
    reseal_refused = False
    try:
        from cmd_chat.sor.provenance import seal_manifest

        seal_manifest(run_dir, recomputed)
    except ValueError:
        reseal_refused = True

    passed = sha_match and reseal_refused
    return GateItem(6, "provenance integrity (events SHA == manifest; append-only)", passed,
                    "green" if passed else "red",
                    {"run_id": run_id, "events_sha256": recomputed,
                     "manifest_events_sha256": sealed["events"]["sha256"],
                     "sha_match": sha_match, "reseal_refused": reseal_refused})


def run_gate(out_dir: Path, *, allow_live: bool = True, e2e_seed: int = 0xA11CE) -> Dict[str, Any]:
    """Re-confirm all six §5 gate items and write ``gate-report.json`` (write-once)
    under ``out_dir``. Returns the report dict. ``all_green`` is True only if every
    item is green; item 1 may be ``unavailable`` when no isolated engine is present,
    which is reported distinctly from a ``red`` failure."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    items: List[GateItem] = [
        _item1_e2e(out_dir, e2e_seed, allow_live=allow_live),
        _item2_reproducible(),
        _item3_correlator(),
        _item4_entropy(),
        _item5_isolation(),
        _item6_provenance(out_dir),
    ]
    all_green = all(it.status == "green" for it in items)
    offline_green = all(it.status == "green" for it in items if it.n != 1)
    report = {
        "schema": "sor-gate-report/1",
        "scope": "RQ1+RQ2 lead-paper path (prereg §5 instrument-validation gate)",
        "generated_utc": _utc_now_iso(),
        "all_green": all_green,
        "offline_items_green": offline_green,
        "items": [{"n": it.n, "name": it.name, "passed": it.passed,
                   "status": it.status, "evidence": it.evidence} for it in items],
    }
    path = out_dir / "gate-report.json"
    if not path.exists():
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["_report_path"] = str(path)
    return report
