"""RQ2-P3 mechanism-instrument calibration gate (`rq2p3-mechanism-prereg.md` §7).

DRY, SYNTHETIC-ONLY calibration of the new ``bridge-federated-pool`` topology: it
assembles circuits from harness-generated per-circuit seeds (NOT a confirmatory data
dir), then reports the four §7 gate items. **No confirmatory record is read** — this
is the same blind-safe discipline as the lead-paper loaders; the confirmatory battery
stays HARD-HELD until the prereg is frozen.

Gate items (§7, re-worded 2026-07-21 pre-freeze — see
``docs/stage-05-rq2p3-gate-clarification.md``; the original items 1–2 encoded the
naive-funnel prior and were mechanically wrong under the ratified posterior):
  1. Reproduce the lead degeneracy ON THE FROZEN ``bridge-federated`` BRANCH (not the
     pool). The lead zero-variance degeneracy is a property of the injective fresh-bridge
     map: unique bridge per circuit seed → unique exit-signature → ``m_i=1`` → ``H_i≈0``,
     constant ``c_i=1/C``. A pool draws WITH REPLACEMENT, so it cannot (and must not) be
     asked to reproduce that; the regression teeth live on the untouched frozen branch.
  2. ``B=1`` boundary — all circuits share the one bridge → ``c=1.0`` (concentration
     tooth kept). Under the RATIFIED posterior the anonymity set is then all circuits
     sharing the exit house, so realized H is at the HIGH end (maximal mix). The naive
     "low H" gloss is refuted by construction; expect high H.
  3. Monotonicity — mean top-3 concentration decreases in B and increases in alpha.
  4. Entropy calibration (inherited) — plug-in entropy of N equiprobable senders is
     exactly log2(N); Miller–Madow adds only the documented finite-N bias term.

SCOPE NOTE: this gate validates the INSTRUMENT and MUST NOT pre-assert the sign of
H-vs-concentration — that sign is the two-sided confirmatory question (H1/H2). The dry
pass previews a mix (ρ 0→+0.838) as an EXPLORATORY finding; the two-sided pre-commitment
in §2 is untouched.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from typing import Dict, List

from cmd_chat.sor.analysis.confirm_load_rq2 import (
    bridge_concentration,
    bridge_label,
    per_circuit_entropy,
    top_k_bridge_concentration,
)
from cmd_chat.sor.analysis.stats import miller_madow_entropy_bits, spearman
from cmd_chat.sor.assembler import assemble
from cmd_chat.sor.battery import Cell, derive_seed, enumerate_rq2p3_cells

R_DRY = 30   # runs/cell for the dry calibration (matches the prereg §6 R)
C_DRY = 50   # circuits/run (matches C)


def _run_circuit_seeds(cell_id: str, run_index: int, c: int = C_DRY) -> List[int]:
    """Harness-side per-circuit seeds for the DRY pass (the confirmatory executor
    persists real per_circuit_seeds; this is calibration only). Deterministic from
    the frozen per-run seed rule so the calibration is reproducible."""
    run_seed = derive_seed(cell_id, run_index)
    return [int.from_bytes(hashlib.sha256(f"{run_seed}|circ|{j}".encode()).digest()[:8], "big")
            for j in range(c)]


def _assemble_run(cell: Cell, run_index: int, c: int = C_DRY):
    return [assemble(cell, s) for s in _run_circuit_seeds(cell.cell_id, run_index, c)]


def _pool_cell(b: int, alpha: float) -> Cell:
    return Cell("RQ2P3", f"RQ2P3/dry/B={b}/alpha={alpha}",
                {"bridge": "off", "topology": "bridge-federated-pool",
                 "selector": "static", "pool_B": str(b), "pool_alpha": str(alpha)}, False)


def _fed_cell() -> Cell:
    """The FROZEN lead ``bridge-federated`` branch (untouched, fresh bridge per circuit
    seed). Item-1 regression teeth live here, not on the pool."""
    return Cell("RQ2", "RQ2/bridge=off/selector=static/topo=bridge-federated",
                {"bridge": "off", "topology": "bridge-federated", "selector": "static"}, False)


def frozen_branch_regression(r: int = R_DRY, c: int = C_DRY) -> Dict:
    """Item 1: the untouched frozen ``bridge-federated`` branch must still show the lead
    degeneracy — unique bridge per circuit (unique exit-signature) → ``m_i=1`` → ``H_i≈0``,
    constant ``c_i=1/C``. Checked per-run (the confirmatory grouping unit)."""
    fed = _fed_cell()
    labels_all_distinct = True
    H_all_zero = True
    c_all_const = True
    mean_h: List[float] = []
    for ri in range(r):
        specs = _assemble_run(fed, ri, c)
        labels = [bridge_label(s) for s in specs]
        labels_all_distinct &= (len(set(labels)) == len(labels))
        ent = per_circuit_entropy(specs)
        mean_h.append(statistics.fmean(ent))
        H_all_zero &= all(h < 1e-9 for h in ent)
        conc = [x for x in bridge_concentration(specs) if x is not None]
        c_all_const &= bool(conc) and all(abs(x - 1.0 / c) < 1e-9 for x in conc)
    return {
        "labels_all_distinct": labels_all_distinct,
        "H_all_zero": H_all_zero,
        "c_all_const_1_over_C": c_all_const,
        "mean_entropy_bits": statistics.fmean(mean_h),
        "pass": labels_all_distinct and H_all_zero and c_all_const,
    }


def cell_report(cell: Cell, r: int = R_DRY, c: int = C_DRY) -> Dict:
    """Per-cell dry report: mean top-3 concentration over runs, pooled per-circuit
    (c_i, H_i) Spearman ρ, and the concentration spread."""
    per_run_top3: List[float] = []
    per_run_mean_h: List[float] = []
    conc_all: List[float] = []
    h_all: List[float] = []
    for ri in range(r):
        specs = _assemble_run(cell, ri, c)
        per_run_top3.append(top_k_bridge_concentration(specs, k=3))
        ent = per_circuit_entropy(specs)
        per_run_mean_h.append(statistics.fmean(ent))
        for ci, hi in zip(bridge_concentration(specs), ent):
            if ci is not None:
                conc_all.append(ci)
                h_all.append(hi)
    b = int(cell.factors["pool_B"])
    alpha = float(cell.factors["pool_alpha"])
    return {
        "B": b,
        "alpha": alpha,
        "mean_top3_concentration": statistics.fmean(per_run_top3),
        "concentration_stdev": statistics.pstdev(conc_all) if conc_all else 0.0,
        "mean_entropy_bits": statistics.fmean(per_run_mean_h),
        "spearman_rho_conc_vs_H": spearman(conc_all, h_all),
        "n_bridged_circuits": len(conc_all),
    }


def calibration_gate(r: int = R_DRY, c: int = C_DRY) -> Dict:
    """Run all four §7 gate items on the DRY pass and return a report dict."""
    sweep = [cr for cr in (cell_report(cell, r, c) for cell in enumerate_rq2p3_cells())]
    grid = {(cr["B"], cr["alpha"]): cr for cr in sweep}

    # Item 1 — regression teeth on the FROZEN bridge-federated branch (not the pool):
    # unique bridge per circuit → unique signature → m_i=1 → H≈0, constant c_i=1/C.
    # The pool anchor B=50,alpha=0 is retained as an EXPLORATORY diagnostic only (it is a
    # mix, ρ>0 — it does NOT and must NOT reproduce the injective fresh-bridge degeneracy).
    fed_reg = frozen_branch_regression(r, c)
    anchor = grid[(50, 0.0)]  # exploratory: pool at B=50 draws WITH replacement → mix
    item1_pass = fed_reg["pass"]

    # Item 2 — B=1 boundary: all circuits share one bridge → c=1.0 (concentration tooth),
    # and under the ratified posterior H is at the HIGH end (maximal mix). Reference =
    # the frozen fresh-bridge branch H (≈0). Passing means c=1.0 AND H high, by construction.
    ext = cell_report(_pool_cell(1, 0.0), r, c)
    fresh_ref_H = fed_reg["mean_entropy_bits"]
    item2_conc_ok = abs(ext["mean_top3_concentration"] - 1.0) < 1e-9
    item2_high_H = ext["mean_entropy_bits"] > fresh_ref_H
    item2_pass = item2_conc_ok and item2_high_H

    # Item 3 — monotonicity: mean top-3 concentration decreasing in B, increasing in alpha.
    dec_in_B = all(
        grid[(2, a)]["mean_top3_concentration"] >= grid[(4, a)]["mean_top3_concentration"] >= grid[(8, a)]["mean_top3_concentration"]
        for a in (0.0, 1.0, 2.0)
    )
    inc_in_alpha = all(
        grid[(b, 0.0)]["mean_top3_concentration"] <= grid[(b, 1.0)]["mean_top3_concentration"] <= grid[(b, 2.0)]["mean_top3_concentration"]
        for b in (2, 4, 8)
    )
    item3_pass = dec_in_B and inc_in_alpha

    # Item 4 — entropy calibration (inherited): plug-in H of N equiprobable = log2(N) exactly.
    entropy_checks = []
    item4_pass = True
    for n in (2, 4, 8, 16, 50):
        mm = miller_madow_entropy_bits([1] * n)
        bias = (n - 1) / (2.0 * n * math.log(2.0))
        plugin = mm - bias
        ok = abs(plugin - math.log2(n)) < 1e-9
        item4_pass = item4_pass and ok
        entropy_checks.append({"N": n, "plugin_bits": plugin, "log2N": math.log2(n),
                               "miller_madow_bits": mm, "plugin_equals_log2N": ok})

    return {
        "schema": "sor-rq2p3-calibration/1",
        "dry_only": True,
        "no_confirmatory_data_read": True,
        "R": r, "C": c,
        "sweep": sweep,
        "gate": {
            "item1_reproduce_lead_degeneracy": {
                "regressed_on": "frozen bridge-federated branch (untouched)",
                "frozen_branch": fed_reg,
                "exploratory_pool_anchor_B50_alpha0": anchor,
                "note": (
                    "Teeth are on the frozen fresh-bridge branch (unique signatures → m_i=1 "
                    "→ H≈0, constant c=1/C). A pool draws WITH replacement so it cannot "
                    "reproduce that; the B=50 pool anchor is an EXPLORATORY mix (ρ>0), not a "
                    "regression target. Re-worded pre-freeze; see "
                    "docs/stage-05-rq2p3-gate-clarification.md."
                ),
                "pass": item1_pass,
            },
            "item2_B1_boundary": {
                "mean_top3_concentration": ext["mean_top3_concentration"],
                "mean_entropy_bits": ext["mean_entropy_bits"],
                "fresh_bridge_reference_mean_entropy_bits": fresh_ref_H,
                "concentration_c_eq_1": item2_conc_ok,
                "entropy_high_maximal_mix": item2_high_H,
                "note": (
                    "B=1 shares one bridge → c=1.0 (concentration tooth) AND, under the "
                    "ratified posterior, the anonymity set is all circuits sharing the exit "
                    "house → H at the HIGH end (maximal mix). The naive 'low H' gloss is "
                    "refuted by construction; expect high H. Re-worded pre-freeze."
                ),
                "pass": item2_pass,
            },
            "item3_monotonicity": {
                "decreasing_in_B": dec_in_B,
                "increasing_in_alpha": inc_in_alpha,
                "pass": item3_pass,
            },
            "item4_entropy_calibration": {
                "checks": entropy_checks,
                "pass": item4_pass,
            },
            "all_pass": bool(item1_pass and item2_pass and item3_pass and item4_pass),
        },
    }


if __name__ == "__main__":
    print(json.dumps(calibration_gate(), indent=2, sort_keys=True))
    sys.exit(0)
