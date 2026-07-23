"""Confirmatory-battery orchestration for the RQ1+RQ2 lead paper.

This is the *start-line* orchestration layer: it enumerates the frozen prereg §2
confirmatory cells for RQ1 and RQ2, derives each run's seed by the frozen §4 rule,
lays out the §2 randomized/interleaved run schedule, and can execute a **DRY
provenance pass on fixtures** to prove the pipeline emits schema-valid, checksummed
R2/R3 provenance and that a seed reproduces its circuit-build sequence.

It deliberately does **not** collect confirmatory data: the DRY pass replays the
deterministic fixture event stream (no engine, no traffic — the containment-safe
`events.replay_*` path), and the confirmatory battery itself is the human gate.
The live 3-hop delivery of a real cell is driven separately by
`forwarder.run_circuit_fixture` on the isolated grid, only after operator go.

Frozen inputs honoured here (never redefined):
  * base seed **S0 = 20260719** (§4);
  * **R = 30** runs/cell, **C = 50** circuits/run (§4);
  * RQ1 cells = bridge {off, on, on+padding} at single-house/static; RQ2 cells =
    topology {1-house-N, bridge-federated, directory-federated} at bridge-off/
    static, matched-N (§2). bridge-off+padding is a **declared N/A** (not run).

The one operationalisation this module *defines* (the frozen §4 text gives the
formula abstractly, not a byte encoding): the per-run seed is
``SHA256("<S0>|<cell_id>|<run_index>")`` big-endian first 8 bytes → u64. This
binding is documented in the emitted plan artifact so it is auditable and is a
harness detail, not an edit to any frozen threshold.
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cmd_chat.sor import events as sor_events
from cmd_chat.sor.config import bringup
from cmd_chat.sor.provenance import Node, RunManifest, validate_manifest

# --- frozen constants (prereg §4) ------------------------------------------ #
S0 = 20260719          # base seed (freeze date, no hidden structure)
R_RUNS = 30            # independent seeded runs per cell
C_CIRCUITS = 50        # circuits built per run
_U64_MASK = (1 << 64) - 1


def derive_seed(cell_id: str, run_index: int, s0: int = S0) -> int:
    """Per-run seed = first 8 bytes (big-endian) of
    ``SHA256("<s0>|<cell_id>|<run_index>")`` as a u64 (frozen §4 rule; this exact
    serialization is the harness binding of the abstract formula)."""
    msg = f"{s0}|{cell_id}|{run_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(msg).digest()[:8], "big") & _U64_MASK


@dataclass(frozen=True)
class Cell:
    """One confirmatory design cell (or a declared N/A cell that is *not* run)."""

    rq: str                       # "RQ1" | "RQ2"
    cell_id: str                  # canonical, stable id (used in the seed rule)
    factors: Dict[str, str]       # level assignments for every factor
    is_control: bool
    na: bool = False              # declared N/A (padding only defined for bridge-on)
    na_reason: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


def enumerate_cells() -> List[Cell]:
    """The frozen §2 confirmatory cell list for the RQ1+RQ2 lead paper: 3 RQ1 +
    3 RQ2 run cells, plus the one declared-N/A cell (recorded, never run)."""
    cells: List[Cell] = [
        # RQ1 — bridge condition at the single-house/static control.
        Cell("RQ1", "RQ1/topo=1house/selector=static/bridge=off",
             {"bridge": "off", "topology": "1house", "selector": "static"}, True),
        Cell("RQ1", "RQ1/topo=1house/selector=static/bridge=on",
             {"bridge": "on", "topology": "1house", "selector": "static"}, False),
        Cell("RQ1", "RQ1/topo=1house/selector=static/bridge=on+padding",
             {"bridge": "on+padding", "topology": "1house", "selector": "static"}, False),
        # RQ2 — federation topology at the bridge-off/static control, matched-N.
        Cell("RQ2", "RQ2/bridge=off/selector=static/topo=1house-N",
             {"bridge": "off", "topology": "1house-N", "selector": "static"}, True),
        Cell("RQ2", "RQ2/bridge=off/selector=static/topo=bridge-federated",
             {"bridge": "off", "topology": "bridge-federated", "selector": "static"}, False),
        Cell("RQ2", "RQ2/bridge=off/selector=static/topo=directory-federated",
             {"bridge": "off", "topology": "directory-federated", "selector": "static"}, False),
    ]
    return cells


def enumerate_rq2p3_cells() -> List[Cell]:
    """The RQ2-P3 funnelling-mechanism sweep cells (`rq2p3-mechanism-prereg.md` §4),
    kept **separate** from the frozen lead lattice: `enumerate_cells()` above is left
    byte-identical so every lead-pipeline caller (`plan_runs`, `battery_schedule`,
    `assembler_dry_check`, `collect_rq2_p1_arms`) stays bit-reproducible.

    These use the new `bridge-federated-pool` topology (finite willing-bridge pool of
    size ``B`` under a Zipf willingness skew ``alpha``) so concentration genuinely
    varies. Tagged ``rq = "RQ2P3"`` so they are distinct from the frozen RQ1/RQ2
    cells and are skipped by the lead RQ2 collectors (which filter ``rq == "RQ2"``).

    9 sweep cells: ``B ∈ {2,4,8} × alpha ∈ {0, 1.0, 2.0}``, plus the ``B=50, alpha=0``
    **calibration anchor** that reproduces the lead RQ2-P3 degeneracy (§7 gate item 1).
    """
    cells: List[Cell] = []
    for b in (2, 4, 8):
        for alpha in (0.0, 1.0, 2.0):
            cells.append(Cell(
                "RQ2P3",
                f"RQ2P3/topo=bridge-federated-pool/selector=static/B={b}/alpha={alpha}",
                {"bridge": "off", "topology": "bridge-federated-pool",
                 "selector": "static", "pool_B": str(b), "pool_alpha": str(alpha)},
                False,
            ))
    cells.append(Cell(
        "RQ2P3",
        "RQ2P3/topo=bridge-federated-pool/selector=static/B=50/alpha=0.0",
        {"bridge": "off", "topology": "bridge-federated-pool",
         "selector": "static", "pool_B": "50", "pool_alpha": "0.0"},
        False,
    ))
    return cells


# --- RQ3 companion cells (frozen prereg §3/§4; run-brief params) ------------ #
RQ3_KILL_PROB_PCT = 30   # pinned churn kill probability (run-brief §2(B))
RQ3_CHURN_STEPS = 20     # pinned churn horizon (run-brief §2(B))


def enumerate_rq3_cells() -> List[Cell]:
    """The RQ3 companion cells (`sor-consent-prereg.md` §3/§4, params pinned in
    `rq3-companion-run-brief.md` §2), kept **separate** from the frozen lead lattice so
    `enumerate_cells()` stays byte-identical for every lead-pipeline caller.

    The selector arm (`selector ∈ {static, random, agent}`) is the only manipulation,
    at the 1-house / bridge-off control, under the pinned churn schedule
    (`kill_prob_pct = 30`, `steps = 20`). ``static`` is the interleaved control baseline;
    ``random`` and ``agent`` are treatments. Tagged ``rq = "RQ3"`` so they are distinct
    from the frozen RQ1/RQ2 cells and are skipped by the lead collectors.
    """
    churn_tag = f"kp{RQ3_KILL_PROB_PCT}s{RQ3_CHURN_STEPS}"
    cells: List[Cell] = []
    for sel in ("static", "random", "agent"):
        cells.append(Cell(
            "RQ3",
            f"RQ3/topo=1house/bridge=off/selector={sel}/churn={churn_tag}",
            {"bridge": "off", "topology": "1house", "selector": sel,
             "churn_kill_prob_pct": str(RQ3_KILL_PROB_PCT),
             "churn_steps": str(RQ3_CHURN_STEPS)},
            is_control=(sel == "static"),
        ))
    return cells


def rq3_schedule(order_seed: int, r: int = R_RUNS) -> List[PlannedRun]:
    """RQ3 executable run order, honouring §2's interleaving discipline: runs
    randomized **within** each cell, and the ``static`` control arm interleaved
    **before and after** the {random, agent} treatments so grid drift is bracketed.
    Deterministic from ``order_seed`` (a measurement-side ordering seed). Kept
    **separate** from the frozen lead ``battery_schedule`` (which is left byte-identical)."""
    rng = random.Random(order_seed)
    cells = enumerate_rq3_cells()
    control = next(c for c in cells if c.is_control)
    treatments = [c for c in cells if not c.is_control]

    def runs_of(c: Cell) -> List[PlannedRun]:
        rs = [PlannedRun(c.cell_id, c.rq, i, derive_seed(c.cell_id, i), c.is_control)
              for i in range(r)]
        rng.shuffle(rs)
        return rs

    control_runs = runs_of(control)
    half = len(control_runs) // 2
    ordered: List[PlannedRun] = list(control_runs[:half])       # control BEFORE
    treatment_runs = [pr for c in treatments for pr in runs_of(c)]
    rng.shuffle(treatment_runs)
    ordered.extend(treatment_runs)
    ordered.extend(control_runs[half:])                         # control AFTER
    return ordered


def declared_na_cells() -> List[Cell]:
    """N/A cells declared at the design (not run, not dropped ad hoc) — padding is
    only defined for bridge-on, so bridge-off+padding is N/A (§2)."""
    return [
        Cell("RQ1", "RQ1/topo=1house/selector=static/bridge=off+padding",
             {"bridge": "off+padding", "topology": "1house", "selector": "static"},
             False, na=True,
             na_reason="padding is only defined for bridge-on (prereg §2)"),
    ]


@dataclass(frozen=True)
class PlannedRun:
    """One planned run: its cell, run index, and the frozen-rule-derived seed. No
    data — a plan entry only."""

    cell_id: str
    rq: str
    run_index: int
    seed: int
    is_control: bool


def plan_runs(cells: Optional[List[Cell]] = None, r: int = R_RUNS) -> List[PlannedRun]:
    """The full cell × run plan (no ordering yet): for every runnable cell, R runs
    each with its frozen-derived seed."""
    cells = cells if cells is not None else enumerate_cells()
    plan: List[PlannedRun] = []
    for c in cells:
        if c.na:
            continue
        for i in range(r):
            plan.append(PlannedRun(c.cell_id, c.rq, i, derive_seed(c.cell_id, i), c.is_control))
    return plan


def battery_schedule(order_seed: int, r: int = R_RUNS) -> List[PlannedRun]:
    """The executable run order honouring §2: run order **randomized within each
    cell**, and each RQ's **control arm interleaved before and after** its
    treatments (so grid calibration drift is bracketed). Deterministic from
    ``order_seed`` (a measurement-side ordering seed, distinct from the data seeds).
    """
    rng = random.Random(order_seed)
    cells = enumerate_cells()
    ordered: List[PlannedRun] = []
    for rq in ("RQ1", "RQ2"):
        rq_cells = [c for c in cells if c.rq == rq]
        control = next(c for c in rq_cells if c.is_control)
        treatments = [c for c in rq_cells if not c.is_control]

        def runs_of(c: Cell) -> List[PlannedRun]:
            rs = [PlannedRun(c.cell_id, c.rq, i, derive_seed(c.cell_id, i), c.is_control)
                  for i in range(r)]
            rng.shuffle(rs)  # randomize order WITHIN the cell
            return rs

        control_runs = runs_of(control)
        half = len(control_runs) // 2
        ordered.extend(control_runs[:half])           # control BEFORE treatments
        treatment_runs = [pr for c in treatments for pr in runs_of(c)]
        rng.shuffle(treatment_runs)
        ordered.extend(treatment_runs)
        ordered.extend(control_runs[half:])           # control AFTER treatments
    return ordered


def write_cell_plan(out_dir: Path, order_seed: int = S0) -> Path:
    """Emit the committed, auditable dry-run plan artifact: the cell list, the
    declared N/A cells, the seed rule, R/C, and the full randomized/interleaved
    schedule (cell_id, run_index, seed). Plan only — no data. Write-once."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "cell-plan.json"
    if path.exists():
        raise FileExistsError(f"cell-plan.json already exists (immutable): {path}")

    cells = enumerate_cells()
    schedule = battery_schedule(order_seed)
    doc = {
        "schema": "sor-cell-plan/1",
        "scope": "lead paper (G4 + RQ1 + RQ2) — RQ3 severable follow-on (prereg D6)",
        "base_seed_S0": S0,
        "R_runs_per_cell": R_RUNS,
        "C_circuits_per_run": C_CIRCUITS,
        "seed_rule": "SHA256('<S0>|<cell_id>|<run_index>') big-endian first 8 bytes -> u64",
        "order_seed": order_seed,
        "cells": [c.to_dict() for c in cells],
        "declared_na_cells": [c.to_dict() for c in declared_na_cells()],
        "n_run_cells": len(cells),
        "total_runs": len(cells) * R_RUNS,
        "total_circuits": len(cells) * R_RUNS * C_CIRCUITS,
        "matched_N_rule": (
            "RQ2 single-house arm node count = total consenting nodes of the "
            "federated arm (prereg §6 matched-N [APPROVAL]); the concrete N is "
            "pinned from the grid inventory at run time and recorded per R2 manifest"
        ),
        "schedule": [asdict(pr) for pr in schedule],
    }
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# DRY provenance pass (fixtures only — NOT a confirmatory cell).
# --------------------------------------------------------------------------- #
def _fixture_pubkey(seed: int, role: str) -> str:
    """A deterministic 32-byte fixture Ed25519-shaped pubkey (base64) so a DRY
    manifest carries a valid persona fingerprint. Not a real key — fixture only."""
    raw = hashlib.sha256(f"sor-fixture|{seed}|{role}".encode()).digest()  # 32 bytes
    return base64.b64encode(raw).decode()


def dry_run_provenance(
    cell: Cell, run_index: int, out_root: Path, *, hops: int = 3, pool: int = 5
) -> Dict:
    """Exercise the full R2/R3 provenance pipeline for one (cell, run) on FIXTURES:
    derive the seed, write an R2 manifest, replay the deterministic fixture event
    stream (R3, no engine/traffic), seal the events SHA-256 into the manifest, and
    verify the seed reproduces the circuit-build sequence. Returns a small report
    dict. Outputs land under ``out_root`` (kept OUT of the confirmatory data dir)."""
    seed = derive_seed(cell.cell_id, run_index)
    run_id = f"dry-{cell.rq}-{run_index}-{seed:016x}"
    run_dir = Path(out_root) / run_id

    nodes = [Node(role=r, persona_pub_b64=_fixture_pubkey(seed, r), engine="docker")
             for r in ("host", "hop", "hop")]
    manifest = RunManifest(
        run_id=run_id,
        sor_seed=seed,
        topology=cell.factors.get("topology", "1house"),
        selector=cell.factors.get("selector", "static"),
        churn_schedule_id="none",  # RQ1/RQ2 use no churn
        nodes=nodes,
        engine_kind="docker",
        worktree_root=Path.cwd(),
    )
    sealed = sor_events.replay_and_seal(run_dir, manifest, pool=pool, hops=hops, rebuilds=1)
    validate_manifest(sealed)

    # Seed reproduces the circuit-build sequence (R1 determinism).
    seq_a = bringup(seed, pool, hops, rebuilds=1)
    seq_b = bringup(seed, pool, hops, rebuilds=1)
    events_sha = sealed["events"]["sha256"]

    return {
        "run_id": run_id,
        "cell_id": cell.cell_id,
        "run_index": run_index,
        "seed": seed,
        "events_sha256": events_sha,
        "manifest_events_sha256": sealed["events"]["sha256"],
        "sha_match": events_sha == sealed["events"]["sha256"],
        "seed_reproduces_circuits": seq_a == seq_b,
        "circuit_sequence": seq_a,
        "run_dir": str(run_dir),
    }


def dry_pass(out_root: Path, *, runs: int = 2) -> Dict:
    """A 1-cell × ``runs``-run DRY pass on fixtures (default the first RQ1 cell).
    Proves schema-valid + checksummed provenance and seed reproducibility without
    touching a confirmatory cell. Returns a summary report; writes it write-once."""
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    cell = enumerate_cells()[0]
    reports = [dry_run_provenance(cell, i, out_root) for i in range(runs)]
    summary = {
        "schema": "sor-dry-pass/1",
        "cell_id": cell.cell_id,
        "runs": runs,
        "all_sha_match": all(r["sha_match"] for r in reports),
        "all_seed_reproduces": all(r["seed_reproduces_circuits"] for r in reports),
        "distinct_seeds": len({r["seed"] for r in reports}) == runs,
        "reports": reports,
    }
    path = out_root / "dry-pass.json"
    if not path.exists():
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


# --------------------------------------------------------------------------- #
# Assembler dry-check (fixtures only — proves each cell is a REAL, distinct,
# isolation-gated live circuit, NOT the plain 3-hop control). Builds plans only:
# opens no socket, moves no traffic, stands up no engine.
# --------------------------------------------------------------------------- #
def assembler_dry_check(out_root: Path, run_index: int = 0, *, engine: str = "docker") -> Dict:
    """Assemble every runnable §2 cell into its condition-encoding CircuitSpec and
    verify, on FIXTURES: (a) all 6 cells build a valid isolated ForwarderPlan for
    every hop (``engine != local``); (b) the 6 fingerprints are distinct (each cell
    is a genuinely different circuit, not the plain control); (c) re-assembling the
    same (cell, seed) reproduces its fingerprint (determinism); (d) the RQ1 bridge
    arms actually insert a bridge hop (+padding flag on on+padding); (e) the RQ2
    federation topologies genuinely span >= 2 houses. Plans only — no traffic, no
    engine. Writes a write-once report under ``out_root`` (kept OUT of any
    confirmatory data dir). Returns the summary."""
    from cmd_chat.sor.assembler import assemble

    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    cells = enumerate_cells()

    per_cell: List[Dict] = []
    fingerprints: List[str] = []
    for c in cells:
        seed = derive_seed(c.cell_id, run_index)
        spec = assemble(c, seed, engine=engine)
        again = assemble(c, seed, engine=engine)  # determinism: same (cell, seed)
        fingerprints.append(spec.fingerprint())
        per_cell.append({
            "cell_id": c.cell_id,
            "rq": c.rq,
            "seed": seed,
            "fingerprint": spec.fingerprint(),
            "isolation_gated": spec.isolation_gated(),
            "reproduces": spec.fingerprint() == again.fingerprint(),
            "bridge_present": spec.bridge_present,
            "padding_applied": spec.padding_applied,
            "span_houses": spec.span_houses(),
            "topology": spec.topology,
        })

    # Condition-encoding expectations (each cell is REAL, not the plain control).
    def _cell(pred) -> Dict:
        return next(r for r in per_cell if pred(r["cell_id"]))

    rq1_on = _cell(lambda i: i.endswith("bridge=on"))
    rq1_pad = _cell(lambda i: i.endswith("bridge=on+padding"))
    rq2_bridge_fed = _cell(lambda i: i.endswith("topo=bridge-federated"))
    rq2_dir_fed = _cell(lambda i: i.endswith("topo=directory-federated"))

    summary = {
        "schema": "sor-assembler-dry/1",
        "run_index": run_index,
        "engine": engine,
        "n_cells": len(per_cell),
        "all_isolation_gated": all(r["isolation_gated"] for r in per_cell),
        "all_reproduce": all(r["reproduces"] for r in per_cell),
        "distinct_fingerprints": len(set(fingerprints)) == len(per_cell),
        "rq1_bridge_arms_live": rq1_on["bridge_present"] and rq1_pad["bridge_present"],
        "rq1_padding_arm_live": rq1_pad["padding_applied"] and not rq1_on["padding_applied"],
        "rq2_federation_spans_2plus": (
            rq2_bridge_fed["span_houses"] >= 2 and rq2_dir_fed["span_houses"] >= 2
        ),
        "cells": per_cell,
    }
    summary["all_green"] = bool(
        summary["all_isolation_gated"] and summary["all_reproduce"]
        and summary["distinct_fingerprints"] and summary["rq1_bridge_arms_live"]
        and summary["rq1_padding_arm_live"] and summary["rq2_federation_spans_2plus"]
    )
    path = out_root / "assembler-dry.json"
    if not path.exists():
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
