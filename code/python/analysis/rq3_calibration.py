"""RQ3 companion instrument-validation gate (`rq3-companion-run-brief.md` §3-4).

DRY, SYNTHETIC-ONLY, OFFLINE calibration of the churn-resilient selector arm. It
replays the pinned churn schedule under each selector strategy via the pure
``run_selection`` (no engine, no traffic, no confirmatory record read) and reports
the RQ3 GO gates that BLOCK the confirmatory battery:

  1. **Churn-bites gate** (§4). At the pinned ``kill_prob_pct = 30``, ``steps = 20``
     the churn must actually bite — circuits genuinely lose hops and rebuild
     (non-zero drops/rebuilds). If the drop rate were trivially zero, the
     throughput-retention and rebuild-classifier tests would be degenerate → STOP.
  2. **Rebuild-classifier calibration gate** (§3.3). Calibrated on labelled control
     signals BEFORE the confirmatory cells: churned (``kp=30``) vs the LOW-CHURN
     baseline (``kp=5``) must be separable on the rebuild-interval-gap signal
     (AUC≈1), while baseline-vs-baseline must be indistinguishable (AUC≈0.5). Not
     fit to confirmatory data.
  3. **Agent-selector reproducibility** (§4). Same seed + churn history → byte-
     identical selector decisions (the deterministic local heuristic arm here; the
     Ollama confirmatory arm is reproducible via its committed decision-cache
     replay, exercised in the unit tests — no network in this gate).
  4. **Entropy calibration (inherited)** — Shannon plug-in of N equiprobable
     senders is exactly log2(N).

HARD HOLD: the confirmatory RQ3 battery does not run until items 1 AND 2 are green
(brief §3-4); this module surfaces, it does not run the battery.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from typing import Dict, List

from cmd_chat.sor.analysis.detectors import shannon_entropy_bits
from cmd_chat.sor.analysis.metrics import rebuild_classifier_auc, throughput_retention
from cmd_chat.sor.battery import derive_seed, enumerate_rq3_cells
from cmd_chat.sor.churn import churn_schedule
from cmd_chat.sor.executor import _rq3_pool, rebuild_interval_gaps
from cmd_chat.sor.selector import run_selection

R_DRY = 30                    # runs/regime for the dry calibration (matches §6 R)
POOL_SIZE = 8                 # 1-house consenting-node pool (> hops, with churn headroom)
HOPS = 3
CHURN_KP = 30                 # pinned confirmatory churn (run-brief §2(B))
CHURN_STEPS = 20              # pinned churn horizon
BASELINE_KP = 5               # LOW-CHURN baseline for the classifier (run-brief §3.3)


def _pool(size: int = POOL_SIZE) -> List[str]:
    return [f"1house/node{ix:02d}" for ix in range(size)]


def _cal_seed(tag: str, i: int) -> int:
    return int.from_bytes(hashlib.sha256(f"rq3-cal|{tag}|{i}".encode()).digest()[:8], "big")


def _replay(seed: int, kp: int, strategy: str = "static", *, steps: int = CHURN_STEPS,
            pool_size: int = POOL_SIZE, hops: int = HOPS):
    nodes = _pool(pool_size)
    sched = churn_schedule(seed, nodes, steps, kill_prob_pct=kp)
    return run_selection(seed, nodes, hops, sched, strategy=strategy)


# --- Item 1: churn-bites ---------------------------------------------------- #
def churn_bites_gate(r: int = R_DRY) -> Dict:
    """At the pinned kp=30/steps=20, confirm the churn bites across every RQ3 cell:
    non-zero drops AND rebuilds, and a healthy fraction of runs that lose a hop."""
    per_cell: List[Dict] = []
    total_drops = 0
    total_rebuilds = 0
    for cell in enumerate_rq3_cells():
        kp = int(cell.factors["churn_kill_prob_pct"])
        steps = int(cell.factors["churn_steps"])
        strategy = cell.factors["selector"]
        drops = 0
        rebuilds = 0
        runs_with_drops = 0
        retentions: List[float] = []
        for ri in range(r):
            seed = derive_seed(cell.cell_id, ri)
            res = _replay(seed, kp, strategy=strategy, steps=steps)
            drops += res.drops
            rebuilds += len(res.rebuilds)
            runs_with_drops += 1 if res.drops > 0 else 0
            retentions.append(throughput_retention(res))
        total_drops += drops
        total_rebuilds += rebuilds
        per_cell.append({
            "cell_id": cell.cell_id,
            "strategy": strategy,
            "total_drops": drops,
            "total_rebuilds": rebuilds,
            "fraction_runs_with_drops": runs_with_drops / r,
            "mean_throughput_retention": statistics.fmean(retentions),
        })
    bites = all(c["total_drops"] > 0 and c["total_rebuilds"] > 0
                and c["fraction_runs_with_drops"] >= 0.5 for c in per_cell)
    return {
        "kill_prob_pct": CHURN_KP,
        "steps": CHURN_STEPS,
        "total_drops": total_drops,
        "total_rebuilds": total_rebuilds,
        "per_cell": per_cell,
        "pass": bool(total_drops > 0 and total_rebuilds > 0 and bites),
    }


# --- Item 2: rebuild-classifier calibration --------------------------------- #
def _per_run_gap_signal(tag: str, kp: int, r: int, strategy: str = "static") -> List[float]:
    """Per-run rebuild-interval signal: the MEAN inter-rebuild gap for each run
    (the confirmatory grouping unit — cf. the RQ2-P3 gate, ``per-run``). Pooling
    raw integer gaps across runs would flood the AUC with tied low integers and
    conflate within- and between-run variation, depressing a genuine signal; per-
    run aggregation is the correct unit and matches how the confirmatory battery
    groups observations. The frozen instrument (``rebuild_interval_gaps``,
    ``rebuild_classifier_auc``) is untouched — this is harness grouping only.
    Runs with <2 rebuilds yield no gap and are omitted (no fabricated interval)."""
    signal: List[float] = []
    for i in range(r):
        res = _replay(_cal_seed(tag, i), kp, strategy=strategy)
        gaps = rebuild_interval_gaps(res)
        if gaps:
            signal.append(statistics.fmean(gaps))
    return signal


def rebuild_classifier_gate(r: int = R_DRY) -> Dict:
    """Churned (kp=30) vs low-churn baseline (kp=5) must be separable on the per-run
    rebuild-interval-gap signal (AUC≈1); baseline-vs-baseline must not (AUC≈0.5).
    Calibrated on labelled control signals, never fit to confirmatory cells."""
    churned = _per_run_gap_signal("churned", CHURN_KP, r)
    baseline = _per_run_gap_signal("baseline", BASELINE_KP, r)
    # Two disjoint baseline halves for the null (same regime → indistinguishable).
    base_a = _per_run_gap_signal("baseline-A", BASELINE_KP, r)
    base_b = _per_run_gap_signal("baseline-B", BASELINE_KP, r)

    auc_sep = rebuild_classifier_auc(churned, baseline)
    auc_null = rebuild_classifier_auc(base_a, base_b)
    separable = auc_sep >= 0.90
    null_ok = abs(auc_null - 0.5) <= 0.15
    return {
        "churned_kill_prob_pct": CHURN_KP,
        "baseline_kill_prob_pct": BASELINE_KP,
        "grouping_unit": "per-run mean inter-rebuild gap",
        "n_churned_runs": len(churned),
        "n_baseline_runs": len(baseline),
        "auc_churned_vs_baseline": auc_sep,
        "auc_baseline_vs_baseline": auc_null,
        "separable_churned_vs_baseline": separable,
        "null_baseline_vs_baseline": null_ok,
        "pass": bool(separable and null_ok),
    }


# --- Item 3: agent-selector reproducibility --------------------------------- #
def agent_reproducibility_gate(r: int = 5) -> Dict:
    """Same seed + churn history → byte-identical selector decisions for the agent
    arm (deterministic local heuristic backend). The Ollama confirmatory arm is
    reproducible via its committed decision-cache replay (tested separately)."""
    all_identical = True
    checks: List[Dict] = []
    for i in range(r):
        seed = _cal_seed("agent-repro", i)
        a = _replay(seed, CHURN_KP, strategy="agent")
        b = _replay(seed, CHURN_KP, strategy="agent")
        same = (a.initial_circuit == b.initial_circuit
                and [rb.circuit for rb in a.rebuilds] == [rb.circuit for rb in b.rebuilds])
        all_identical = all_identical and same
        checks.append({"seed": seed, "identical": same})
    return {"runs": r, "checks": checks, "pass": bool(all_identical)}


# --- Item 4: entropy calibration (inherited) -------------------------------- #
def entropy_calibration() -> Dict:
    checks: List[Dict] = []
    ok = True
    for n in (2, 4, 8, 16, 50):
        h = shannon_entropy_bits({f"s{ix}": 1 for ix in range(n)})
        item_ok = abs(h - math.log2(n)) < 1e-9
        ok = ok and item_ok
        checks.append({"N": n, "shannon_bits": h, "log2N": math.log2(n), "equals": item_ok})
    return {"checks": checks, "pass": bool(ok)}


def calibration_gate(r: int = R_DRY) -> Dict:
    """Run all four RQ3 §3-4 gate items on the DRY/offline pass and return a report."""
    item1 = churn_bites_gate(r)
    item2 = rebuild_classifier_gate(r)
    item3 = agent_reproducibility_gate()
    item4 = entropy_calibration()
    return {
        "schema": "sor-rq3-calibration/1",
        "dry_only": True,
        "offline_no_engine_no_traffic": True,
        "no_confirmatory_data_read": True,
        "R": r,
        "gate": {
            "item1_churn_bites": item1,
            "item2_rebuild_classifier": item2,
            "item3_agent_reproducibility": item3,
            "item4_entropy_calibration": item4,
            "all_pass": bool(item1["pass"] and item2["pass"] and item3["pass"] and item4["pass"]),
        },
    }


if __name__ == "__main__":
    print(json.dumps(calibration_gate(), indent=2, sort_keys=True))
    sys.exit(0)
