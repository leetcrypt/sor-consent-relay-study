"""RQ3 confirmatory analysis — reads the SEALED live-docker battery, applies the
FROZEN prereg §6 plan, and computes the authoritative Holm-7 over the whole family.

This is the RQ3 analogue of ``rq2p3_confirm.py``: it does **not** re-specify anything.
It loads the immutable ``rq3-battery-results.json`` (the operator-gated live-docker
run) and the pinned params in ``docs/rq3-companion-run-brief.md`` and computes the three
frozen RQ3 confirmatory tests, each as an **effect + BCa 95% CI** (never a bare p; the p
is carried only to order the Holm family, per prereg §6):

  * **RQ3-P1-perf** — throughput-retention margin: mean retention(agent) −
    max(mean retention(static), mean retention(random)); perf holds iff the CI **lower**
    bound ≥ +10 pp (frozen gate).
  * **RQ3-P1-latency** — added-latency(agent) = median e2e latency(agent) −
    min(median latency(static), median latency(random)) [the faster / min-latency baseline
    arm, run-brief §3.2]; anonymity-latency budget holds iff the CI **upper** bound ≤ 100 ms.
  * **RQ3-P2** — rebuild-classifier AUC separating the agent selector's per-run mean
    inter-rebuild-gap signal from the pooled baseline selectors' signal (the fingerprint
    question, §1(b)); anonymity holds iff the CI **upper** bound ≤ 0.60.
  * **RQ3-P3** — logical AND: CONFIRM iff (P1-perf ∧ P1-latency) ∧ P2; else H0.

The BCa machinery is the frozen ``stats`` toolkit — this harness only *drives* it at the
run level (resample whole runs, the confirmatory grouping unit) via a generic multi-arm
bootstrap that mirrors ``stats.two_sample_diff_ci`` (independent per-arm resampling, a
combined leave-one-out jackknife, ``stats._bca_endpoints``). No frozen instrument is edited.

**Authoritative Holm-7.** Once all seven confirmatory p-values exist, this computes the
exact ``stats.holm_bonferroni`` step-down over the frozen size-7 family
{RQ1-P1, RQ1-P2, RQ2-P1, RQ2-P3, RQ3-P1-perf, RQ3-P1-latency, RQ3-P2}. The four prior
p-values are read from the SEALED lead record (RQ1-P1, RQ1-P2, RQ2-P1) and the SEALED
RQ2-P3′ mechanism record (RQ2-P3 slot = its primary H1-pooled Spearman ρ — the direct
operationalization of the frozen single-slot "Spearman ρ between concentration and H";
the lead's degenerate as-instrumented RQ2-P3 is superseded by the mechanism-corrected
result, per operator decision D3). This Holm-7 is the authoritative final correction and
supersedes the lead paper's deliberately conservative *partial* embedding; both remain
valid, the partial never under-corrects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Sequence

from cmd_chat.sor.analysis import stats
from cmd_chat.sor.analysis.metrics import rebuild_classifier_auc

# --- frozen family + gates -------------------------------------------------- #
FAMILY_SIZE = 7
FROZEN_FAMILY = (
    "RQ1-P1", "RQ1-P2", "RQ2-P1", "RQ2-P3",
    "RQ3-P1-perf", "RQ3-P1-latency", "RQ3-P2",
)
PERF_MARGIN_MIN_PP = 0.10   # RQ3-P1-perf gate: CI lower ≥ +10 pp
LATENCY_MAX_MS = 100.0      # RQ3-P1-latency gate: CI upper ≤ 100 ms
AUC_CEILING = 0.60          # RQ3-P2 gate: CI upper ≤ 0.60

# sealed prior records (immutable) that carry the 4 non-RQ3 family p-values
LEAD_RESULTS = "output/sor-confirmatory/20260720T060132Z/analysis/stage06-results.json"
RQ2P3_RESULTS = "output/sor-rq2p3-confirmatory/rq2p3-confirmatory-results.json"


def _seed(tag: str) -> int:
    """Deterministic, auditable per-test resampling seed."""
    return int.from_bytes(hashlib.sha256(f"sor-rq3-confirm|{tag}".encode()).digest()[:8], "big")


# --- generic run-level multi-arm bootstrap (mirrors stats.two_sample_diff_ci) --- #
def _multi_arm_bootstrap(
    arms: Dict[str, Sequence[float]],
    statistic: Callable[[Dict[str, List[float]]], float],
    *,
    null: float,
    seed: int,
    n_resamples: int = stats.DEFAULT_RESAMPLES,
    alpha: float = stats.DEFAULT_ALPHA,
):
    """Bootstrap CI + Holm-ordering p for a statistic over >=1 independent arms.

    Each arm is resampled with replacement independently (the frozen two-sample rule
    generalized to N arms); BCa uses a combined leave-one-out jackknife (each point
    dropped from its OWN arm, others full), exactly as ``stats.two_sample_diff_ci``.
    The p is ``stats.two_sided_bootstrap_p`` against ``null`` — carried only to order
    the Holm family, never as a stand-alone decision.
    """
    import random

    names = list(arms)
    data = {k: list(v) for k, v in arms.items()}
    theta_hat = float(statistic(data))
    rng = random.Random(seed)
    thetas: List[float] = []
    for _ in range(n_resamples):
        sample = {k: [v[rng.randrange(len(v))] for _ in range(len(v))] for k, v in data.items()}
        thetas.append(float(statistic(sample)))
    thetas.sort()

    # combined jackknife: drop point i from arm `name`, keep the others full
    can_bca = all(len(v) > 1 for v in data.values())
    if can_bca:
        jack: List[float] = []
        for name in names:
            n = len(data[name])
            for i in range(n):
                d = dict(data)
                d[name] = [data[name][j] for j in range(n) if j != i]
                jack.append(float(statistic(d)))
        q_lo, q_hi, used = stats._bca_endpoints(thetas, theta_hat, jack, alpha)
    else:
        q_lo, q_hi, used = alpha / 2.0, 1.0 - alpha / 2.0, "percentile"

    ci = stats.CIResult(theta_hat, stats._percentile(thetas, q_lo),
                        stats._percentile(thetas, q_hi), alpha, n_resamples, used, seed)
    p = stats.two_sided_bootstrap_p(thetas, null)
    return ci, p


# --- battery loading -------------------------------------------------------- #
def load_battery(path: Path) -> Dict[str, Dict[str, List[float]]]:
    """Load the sealed battery into per-arm {retention, latency, gap_signal}.

    ``gap_signal`` is the per-run MEAN inter-rebuild gap — the confirmatory grouping
    unit (same unit the frozen calibration gate used); runs with no gap are omitted
    (no fabricated interval). Retention/latency are the per-run DVs as measured.
    """
    doc = json.loads(Path(path).read_text())
    arms: Dict[str, Dict[str, List[float]]] = {}
    for _cid, cell in doc["cells"].items():
        arms[cell["strategy"]] = {
            "retention": list(cell["throughput_retention"]),
            "latency": list(cell["added_latency_ms"]),
            "gap_signal": [],
        }
    gap: Dict[str, List[float]] = defaultdict(list)
    for run in doc["runs"]:
        strat = run["cell_id"].split("selector=")[1].split("/")[0]
        gaps = run.get("rebuild_gaps") or []
        if gaps:
            gap[strat].append(statistics.fmean(gaps))
    for strat, sig in gap.items():
        arms[strat]["gap_signal"] = sig
    return arms


# --- the three frozen RQ3 tests --------------------------------------------- #
def _perf_margin(a: Dict[str, List[float]]) -> float:
    return stats.mean(a["agent"]) - max(stats.mean(a["static"]), stats.mean(a["random"]))


def _added_latency(a: Dict[str, List[float]]) -> float:
    # added-latency over the MIN-latency (faster) baseline arm, run-brief §3.2
    return statistics.median(a["agent"]) - min(statistics.median(a["static"]), statistics.median(a["random"]))


def _p2_auc(a: Dict[str, List[float]]) -> float:
    # fingerprint question: agent's per-run rebuild-gap signal vs the pooled baseline
    return rebuild_classifier_auc(a["agent"], a["baseline"])


def analyze_rq3(arms: Dict[str, Dict[str, List[float]]], *, n_resamples: int = stats.DEFAULT_RESAMPLES) -> Dict:
    ret = {k: arms[k]["retention"] for k in ("agent", "static", "random")}
    lat = {k: arms[k]["latency"] for k in ("agent", "static", "random")}
    pool_baseline = arms["static"]["gap_signal"] + arms["random"]["gap_signal"]
    p2_arms = {"agent": arms["agent"]["gap_signal"], "baseline": pool_baseline}

    perf_ci, perf_p = _multi_arm_bootstrap(ret, _perf_margin, null=0.0,
                                           seed=_seed("perf"), n_resamples=n_resamples)
    lat_ci, lat_p = _multi_arm_bootstrap(lat, _added_latency, null=0.0,
                                         seed=_seed("latency"), n_resamples=n_resamples)
    p2_ci, p2_p = _multi_arm_bootstrap(p2_arms, _p2_auc, null=0.5,
                                       seed=_seed("p2-auc"), n_resamples=n_resamples)

    perf_hold = perf_ci.lo >= PERF_MARGIN_MIN_PP           # gate: CI lower ≥ +10 pp
    lat_hold = lat_ci.hi <= LATENCY_MAX_MS                 # gate: CI upper ≤ 100 ms
    p2_hold = p2_ci.hi <= AUC_CEILING                      # gate: CI upper ≤ 0.60
    p1_hold = perf_hold and lat_hold
    p3_confirm = p1_hold and p2_hold

    which_lat_baseline = "random" if statistics.median(lat["random"]) <= statistics.median(lat["static"]) else "static"
    return {
        "RQ3-P1-perf": {
            "effect": "throughput_retention_margin_agent_minus_max_baseline",
            **perf_ci.as_dict(), "p_for_holm": perf_p,
            "gate": f"CI lower ≥ +{PERF_MARGIN_MIN_PP}", "holds": bool(perf_hold),
            "decision": "perf-gain" if perf_hold else "no-perf-gain",
        },
        "RQ3-P1-latency": {
            "effect": "added_latency_ms_agent_minus_min_baseline",
            "min_latency_baseline_arm": which_lat_baseline,
            **lat_ci.as_dict(), "p_for_holm": lat_p,
            "gate": f"CI upper ≤ {LATENCY_MAX_MS} ms", "holds": bool(lat_hold),
            "decision": "within-latency-budget" if lat_hold else "over-latency-budget",
        },
        "RQ3-P2": {
            "effect": "rebuild_classifier_auc_agent_vs_pooled_baseline",
            "grouping_unit": "per-run mean inter-rebuild gap",
            "n_agent_runs": len(p2_arms["agent"]), "n_baseline_runs": len(p2_arms["baseline"]),
            **p2_ci.as_dict(), "p_for_holm": p2_p,
            "gate": f"CI upper ≤ {AUC_CEILING}", "holds": bool(p2_hold),
            "decision": "no-usable-fingerprint" if p2_hold else "fingerprint-not-excluded",
        },
        "RQ3-P3-joint": {
            "rule": "CONFIRM iff (P1-perf ∧ P1-latency) ∧ P2",
            "p1_holds": bool(p1_hold), "p2_holds": bool(p2_hold),
            "confirm": bool(p3_confirm),
            "decision": "agent-helps-without-fingerprint" if p3_confirm else "H0",
        },
    }


# --- authoritative Holm-7 --------------------------------------------------- #
def _load_prior_pvalues(lead_path: Path, rq2p3_path: Path) -> Dict[str, Dict]:
    lead = json.loads(Path(lead_path).read_text())["confirmatory"]
    rq2p3 = json.loads(Path(rq2p3_path).read_text())["results"]
    h1 = rq2p3["H1_pooled_spearman"]
    return {
        "RQ1-P1": {"p": lead["RQ1-P1"]["p_for_holm"], "source": "sealed lead RQ1-P1"},
        "RQ1-P2": {"p": lead["RQ1-P2"]["p_for_holm"], "source": "sealed lead RQ1-P2"},
        "RQ2-P1": {"p": lead["RQ2-P1"]["p_for_holm"], "source": "sealed lead RQ2-P1 (shrink)"},
        "RQ2-P3": {"p": h1["p_for_holm"],
                   "source": "sealed RQ2-P3′ H1-pooled Spearman ρ (mechanism-corrected, mix) "
                             "— supersedes the lead's degenerate as-instrumented RQ2-P3"},
    }


def authoritative_holm7(rq3: Dict, lead_path: Path, rq2p3_path: Path) -> Dict:
    prior = _load_prior_pvalues(lead_path, rq2p3_path)
    pvals = {
        "RQ1-P1": prior["RQ1-P1"]["p"],
        "RQ1-P2": prior["RQ1-P2"]["p"],
        "RQ2-P1": prior["RQ2-P1"]["p"],
        "RQ2-P3": prior["RQ2-P3"]["p"],
        "RQ3-P1-perf": rq3["RQ3-P1-perf"]["p_for_holm"],
        "RQ3-P1-latency": rq3["RQ3-P1-latency"]["p_for_holm"],
        "RQ3-P2": rq3["RQ3-P2"]["p_for_holm"],
    }
    assert set(pvals) == set(FROZEN_FAMILY), "family must be exactly the frozen size-7"
    holm = stats.holm_bonferroni(pvals, family_size=FAMILY_SIZE)
    rows = [{"name": h.name, "raw_p": h.p, "holm_p": h.p_adjusted,
             "multiplier": h.multiplier, "rank": h.rank, "reject": h.reject} for h in holm]
    return {
        "family_size": FAMILY_SIZE,
        "family": list(FROZEN_FAMILY),
        "p_sources": {k: prior[k]["source"] for k in prior},
        "rows": rows,
        "survivors": [r["name"] for r in rows if r["reject"]],
        "non_survivors": [r["name"] for r in rows if not r["reject"]],
        "supersedes": "lead paper's conservative partial embedding (report-4 of family-of-7); "
                      "both valid, partial never under-corrects; RQ1-P1 and RQ2-P1 survive regardless",
    }


def run(*, battery_path: Path, lead_path: Path, rq2p3_path: Path,
        n_resamples: int = stats.DEFAULT_RESAMPLES) -> Dict:
    arms = load_battery(battery_path)
    rq3 = analyze_rq3(arms, n_resamples=n_resamples)
    holm7 = authoritative_holm7(rq3, lead_path, rq2p3_path)
    battery_sha = hashlib.sha256(Path(battery_path).read_bytes()).hexdigest()
    return {
        "schema": "sor-rq3-confirmatory/1",
        "measured_from": "live-docker-e2e",
        "battery_results_path": str(battery_path),
        "battery_results_sha256": battery_sha,
        "n_runs_per_arm": {k: len(arms[k]["retention"]) for k in arms},
        "frozen_lead_prereg_sha256": "f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b",
        "results": rq3,
        "authoritative_holm7": holm7,
        "honest_disclosure": (
            "Every RQ3 test reports effect + BCa 95% CI; p is carried ONLY to order the Holm "
            "family (prereg §6). Nulls are results: a selector that does not beat baselines, or "
            "a rebuild pattern that is not certifiably non-classifiable, is the finding — not spun. "
            "Reproducibility caveat (accepted, run-brief §2A): the agent (qwen2.5:3b via local "
            "Ollama, temp 0) is reproducible via its committed decision-log + (seed, state-hash) "
            "cache replay, NOT via independent model re-execution on other hardware."
        ),
    }


def _seal(out_dir: Path, report: Dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "rq3-confirmatory-analysis.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (out_dir / "SHA256SUMS").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m cmd_chat.sor.analysis.rq3_confirm")
    ap.add_argument("--battery", required=True)
    ap.add_argument("--lead", default=LEAD_RESULTS)
    ap.add_argument("--rq2p3", default=RQ2P3_RESULTS)
    ap.add_argument("--out", default=None)
    ap.add_argument("--n-resamples", type=int, default=stats.DEFAULT_RESAMPLES)
    args = ap.parse_args(argv)
    report = run(battery_path=Path(args.battery), lead_path=Path(args.lead),
                 rq2p3_path=Path(args.rq2p3), n_resamples=args.n_resamples)
    if args.out:
        path = _seal(Path(args.out), report)
        print(f"sealed -> {path}", file=sys.stderr)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
