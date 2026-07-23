# Stage-06 analysis — frozen §6 confirmatory pass on the real 180-cell battery

**Status: CONFIRMATORY (single pre-registered pass). Run once, on the frozen raw
data, after blinding was lifted at battery completion.** This note reports the
four lead-paper confirmatory tests (RQ1-P1, RQ1-P2, RQ2-P1, RQ2-P3) exactly as the
frozen prereg §6 defines them. It does **not** edit the frozen prereg
(`sor-consent-prereg.md`, SHA
`f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b`).

Every number here is regenerable, deterministically, from the frozen raw data:

```
python -m cmd_chat.sor.analysis.stage06_run \
  output/sor-confirmatory/20260720T060132Z/confirmatory-data \
  --out output/sor-confirmatory/20260720T060132Z/analysis/stage06-results.json
```

- Machine-readable results: `output/sor-confirmatory/20260720T060132Z/analysis/stage06-results.json`
- Analysis seed = S0 = `20260719` (fixed pre-data, §4); 10 000 BCa bootstrap
  resamples; α = 0.05; Holm over the frozen size-7 family, reporting 4.

## Headline: this is an honest-null / honest-negative result set

**Neither of the study's hoped-for effects is confirmed, and the one Holm-significant
directional effect points the *opposite* way to the design's motivation.** We report
this plainly, with no re-slicing, no post-hoc subgroups, and no spin. Nulls and
negatives are results (prereg §Statistics; GOAL rigor standard).

| Test | Effect | Point | 95% CI (BCa) | Frozen decision | raw p | Holm adj-p (m=7) | Reject @ .05 |
|---|---|---|---|---|---|---|---|
| RQ1-P1 | AUC (bridge-on) | 0.4660 | [0.4523, 0.4798] | **anomaly-below-chance** | 0.000 | 0.000 | yes* |
| RQ2-P1 | ΔH (fed − single) | −0.9587 bits | [−1.0559, −0.8641] | **shrink** | 0.000 | 0.000 | yes |
| RQ1-P2 | ΔAUC (nopad − pad) | +0.0113 | [−0.0025, +0.0234] | **padding-ineffective** | 0.0912 | 0.456 | no |
| RQ2-P3 | Spearman ρ | 0.0000 | [0.0000, 0.0000] | **inconclusive** | 1.000 | 1.000 | no |

Holm rows are ordered by ascending raw p (multipliers 7, 6, 5, 4). Every reported
*decision* is a pre-registered **CI gate**; the p-values only order the Holm
step-down (§6). `*` see RQ1-P1 below — the rejection is of `H0: AUC = 0.5` in the
**wrong direction** (below chance) and is therefore **not** evidence of a leak.

## Sanity gate — correlator calibration (§5 gate item 3): PASS

Computed independently of the confirmatory data, on the §5 synthetic fixtures
(40 seeds):

- known-linked mean AUC = **1.0000** (criterion ≥ 0.95) ✅
- known-unlinked mean AUC = **0.5036** (criterion 0.40–0.60) ✅

The correlator is calibrated, so the measured AUCs are reportable. Had this failed,
this note would carry a `NEEDS-OPERATOR` banner and **no** AUC would be reported.

## RQ1-P1 — bridge linkability leak: NOT confirmed (null for the leak hypothesis)

- Unit (§4): the (entry, exit) circuit-segment pair; AUC over the pooled pair set of
  the bridge-on / no-pad arm (n = **75 000** pairs, 1 500 linked / 73 500 unlinked),
  BCa 95% CI bootstrapped over pairs.
- **AUC = 0.4660, CI [0.4523, 0.4798].** The CI excludes 0.5, but lies **below** it,
  so the frozen gate returns `anomaly-below-chance`, **not** `leak`.
- **Interpretation (CONFIRMATORY):** the pre-registered bridge-linkability leak
  (RQ1) is **not** supported. The correlator does not link entry↔exit segments
  better than chance on the instrument's bridge-on traffic; it sits marginally
  *below* chance. Rejecting the two-sided null at AUC = 0.5 in the low direction is
  an artifact of the pooled correlator on this as-instrumented traffic, **not** a
  linkability finding. (Note: this is the bridge-on **no-pad** arm —
  `padding_applied = (bridge == "on+padding")` in `assembler.py`, so **no** cover
  stream is present here; the below-chance reading is an unexplained correlator
  artifact, not a padding effect.) We report **no measurable leak**.

### Method note — RQ1-P1 CI is method-faithful, not method-substituted

The frozen `stats.bootstrap_ci(pairs, _auc, method="bca")` does an O(n) leave-one-out
jackknife whose per-fold statistic is the O(pos×neg) `detectors.auc` — structurally
intractable at n = 75 000 (≈ days). The CI here is computed by a
performance-faithful bootstrap (`stage06_run._bootstrap_auc_ci`) that reproduces
`stats.bootstrap_ci` **bit-for-bit**: the same `random.Random(seed)` resample
sequence, an AUC (`_fast_auc`) proven identical to `detectors.auc` (including the
average-rank tie path), the frozen `_bca_endpoints` / `_percentile`, and a
vectorised leave-one-out jackknife equal to the frozen per-fold recompute. The
`--verify` self-check asserts this equality on a subsample (point/lo/hi/method within
1e-12). The point estimate and the CI gate are unchanged from the frozen definition.

## RQ2-P1 — federation anonymity-set effect: CONFIRMED **NEGATIVE** (federation shrinks)

- Unit (§4): the circuit; per-circuit Miller–Madow entropy H over the ratified
  observation-consistent sender posterior (uniform mass over the anonymity set
  A_i sharing an exit signature within a run). Two-sided ΔH = mean H(federated) −
  mean H(single-house, matched N), BCa CI over circuits (frozen
  `confirm.rq2_p1_delta_h`, unchanged).
- Arms: federated = pooled **bridge-federated + directory-federated** (3 000
  circuits, per the loader frozen while blind); single-house = **1house-N** (1 500
  circuits). Matched-N per §6.
- **ΔH = −0.9587 bits, CI [−1.0559, −0.8641].** CI strictly < 0 → frozen gate =
  `shrink`. Holm-adjusted p ≈ 0 (rank 2, multiplier 6) → rejected.
- **Interpretation (CONFIRMATORY):** federation, as instrumented, **reduces** the
  per-circuit anonymity set by ≈ 0.96 bits relative to a matched-N single house.
  This is the *opposite* of RQ2's motivating hypothesis (that federation grows the
  anonymity set). The prereg framed RQ2-P1 two-sided precisely so this outcome is
  reported "with equal prominence" (§6) — it is a genuine negative finding, not a
  failure to detect. We do **not** re-frame it as federation "helping."

## RQ1-P2 — padding efficacy: inconclusive (padding-ineffective)

- Unit: the run-index-paired bridge-on / no-pad vs bridge-on / +padding arms
  (RATIFIED stage-05 pairing), one `PairedCircuit` per shared run index (n = **30**
  paired runs), paired ΔAUC = AUC(no-pad) − AUC(+pad), effective iff CI > 0.
- **ΔAUC = +0.0113, CI [−0.0025, +0.0234].** CI spans 0 → frozen gate =
  `padding-ineffective`. raw p = 0.0912, Holm-adjusted p = 0.456 → not rejected.
- **Interpretation (CONFIRMATORY):** no significant padding effect on measured
  linkability. This is moot given RQ1-P1 found no leak to suppress, but is reported
  as the frozen test specifies. The per-run ΔAUC diagnostics (30 values, in the
  results JSON) straddle zero (range ≈ [−0.080, +0.081]), consistent with the null.
- Same intractability as RQ1-P1 (each resample pools ~75 k pairs through the O(n²)
  frozen `auc` twice); the CI uses the bit-faithful `_bootstrap_delta_auc_ci`,
  `--verify`-checked equal to `stats.bootstrap_ci(units, _delta_auc, bca)` bit-for-bit.

## RQ2-P3 — funnelling mechanism: inconclusive (as-instrumented degeneracy)

- Unit: per bridge-federated circuit — Spearman ρ between top-k = 3 willing-bridge
  concentration and per-circuit H (frozen `confirm.rq2_p3_funnel`, k = 3;
  n = 1 500 circuits).
- **ρ = 0.0000, CI [0.0000, 0.0000]** (percentile fallback) → `inconclusive`.
- **Interpretation (CONFIRMATORY):** the concentration series has **no variance** —
  the bridge-federated topology assigns a *fresh* willing bridge per circuit seed, so
  willing-bridge reuse is minimal and the top-3 concentration is effectively
  constant. Spearman is undefined on a zero-variance covariate and returns 0. This is
  the **as-instrumented degeneracy flagged in advance** (stage-05 RQ2 clarification
  instrument caveat), not a null effect of a well-posed mechanism test. The
  funnelling mechanism is **not testable** on this instrument as built; we report it
  as inconclusive and carry the caveat into Limitations rather than over-claiming.

## Multiplicity (Holm–Bonferroni, frozen family size 7, report 4)

Ordered by ascending raw p; multipliers are `7 − k + 1` for reported rank k
(conservative embedding — the reported RQ1/RQ2 tests occupy the smallest slots of
the full frozen family; never re-optimised to m = 4). Two tests survive Holm at
α = 0.05: RQ1-P1 (anomaly-below-chance — *not* a leak) and RQ2-P1 (shrink — a
negative effect). RQ1-P2 and RQ2-P3 do not.

## Exploratory (labelled EXPLORATORY — not Holm-corrected, not confirmatory)

- **RQ2-P1, bridge-federated-only ΔH** = −3.63 bits (degenerate CI; every resample
  identical because the bridge-federated per-circuit posterior is near-single-member,
  m_i ≈ 1). This is the directive's narrower contrast; it is reported only for
  transparency and reinforces the RQ2-P3 degeneracy note (the bridge-federated arm's
  anonymity set is near-trivial as instrumented). It carries **no** confirmatory
  weight and is excluded from the Holm family.

## What this pass did and did not do

- **Ran only the pre-registered tests.** No exploratory subgroup hunting, no
  re-slicing of cells, no alternative estimators. The one exploratory contrast is
  labelled and severed from the confirmatory family.
- **Definitions are the frozen ones.** RQ1-P1 = bridge-on AUC vs 0.5 (D2), *not* the
  bridge-on−bridge-off contrast paraphrased in the drive prompt; where the two
  differed, the frozen prereg governs.
- **Blinding.** This is the first inferential pass; SS2 (raw freeze) computed no
  AUC/H/CI. The correlator/entropy calibration was fixed on §5 synthetic fixtures
  only — never fit to confirmatory-cell data.
- **Reproducibility.** Deterministic (fixed seed); the committed
  `stage06_run.py --verify` proves the two fast bootstraps equal the frozen
  `stats.bootstrap_ci` bit-for-bit, so the fast paths introduce no method artifact.
