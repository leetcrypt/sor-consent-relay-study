# Pre-registration (DRAFT) — RQ2-P3 funnelling-mechanism study

> **STATUS: FROZEN — operator freeze sign-off 2026-07-21** (Andre delegated per-gate command
> authorization to the overseer 2026-07-21; executed by overseer). Design + parameters
> operator-approved 2026-07-21 (grid B∈{2,4,8}×α∈{0,1,2}; run-level cluster bootstrap;
> two-sided/direction-agnostic). The SHA-256 of this file is recorded in
> `rq2p3-mechanism-prereg.sha256` (§10). The confirmatory battery MAY now run; no hypothesis or
> parameter may change post-freeze.
> This is a **new study with its own slug** (`sor-consent-rq2p3`). It **does not modify**
> the frozen lead prereg (`sor-consent-prereg.md`, SHA
> `f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b`), whose RQ2-P3
> result stands as reported ("inconclusive — not testable as-instrumented").

## 0. Why this study exists

The lead paper found federation **shrinks** the per-circuit anonymity set (RQ2-P1,
ΔH = −0.96 bits, Holm-significant) but could **not** test the *mechanism* (RQ2-P3): the
bridge-federated instrument assigns a **fresh willing bridge per circuit seed**
(`assembler.py:131`, `_bridge_label(seed)`), so every circuit routes through a distinct
bridge, top-3 concentration is constant (`c_i = 1/C`), the covariate has **zero variance**,
and Spearman ρ is undefined (`stats.spearman` returns 0.0 by construction). The lead paper
reported this honestly as an as-instrumented degeneracy, not a null of a well-posed test.

**The mechanical insight this study exists to test (see `note-unique-bridge-artifact.md`).**
The adversary's observation is `exit_signature = (exit_house, bridge_label)`, and the
per-circuit anonymity set `m_i` = the distinct entry nodes among circuits sharing that
signature (`confirm_load_rq2.py`). A **fresh bridge per circuit ⇒ every signature is unique
⇒ group size 1 ⇒ m_i = 1 ⇒ H ≈ 0.** That — not funnelling — is why bridge-federated produced
H ≈ 0 and drove the lead ΔH negative. Introduce a **finite shared pool** and many circuits
share a bridge ⇒ shared signature ⇒ larger set ⇒ **higher H**. Under this posterior a bridge
is a **mix**: more concentration plausibly *raises* anonymity, the opposite of the naive
funnel story. So this study is, honestly, **a test of whether the lead paper's "shrink" is a
unique-bridge artifact** — and it may *qualify or correct* the lead RQ2-P1 headline.

This study re-instruments the willing-bridge layer with a **finite pool + skewed
willingness** so concentration genuinely varies, and — the key upgrade — treats
concentration as a **manipulated independent variable** (a dose-response design) rather than
a passive covariate. The direction is left **two-sided**: the naive prediction is funnel
(ρ < 0); the mechanical prediction under the ratified posterior is mix (ρ > 0). We pre-commit
to reporting whichever the data shows, including a correction to the lead result if warranted.
The analysis code (`bridge_concentration`, `rq2_p3_funnel`) is already correct; only the
*instrument* and this *prereg* are new.

## 1. Blinding & integrity posture (read first)

- **This study is NOT blind to the RQ2-P1 shrink direction** (the lead paper is published).
  Mitigations that keep it honest: (a) the funnelling hypothesis was **pre-stated as a live
  mechanism** in the lead paper's introduction, not invented post-hoc; (b) the confirmatory
  targets below are **two-sided**; (c) concentration is a *manipulated* IV, so the test is a
  designed dose-response, not a re-slice of the lead data.
- **The lead RQ2-P1 result is NOT re-litigated here.** Any ΔH this pool instrument produces
  is labeled **EXPLORATORY / replication**, never a re-run of the frozen RQ2-P1.
- **No detector retuning.** The entropy estimator, posterior construction, and Spearman path
  are inherited **unchanged** from the frozen lead pipeline; only bridge assignment changes.

## 2. Research question & hypotheses

**RQ2-P3′.** Within the consent-gated bridge-federated topology, does willing-bridge
**concentration** causally reduce the per-circuit anonymity set (funnelling)?

- **H1 (within-cell association, two-sided).** Spearman ρ between per-circuit top-3 willing-
  bridge concentration `c_i` and per-circuit entropy `H_i`. **Funnel** iff BCa 95% CI < 0;
  **mix** iff CI > 0; **inconclusive** iff CI spans 0. Direction is *not* presumed.
- **H2 (dose-response, two-sided).** OLS slope β of H on realized top-3 concentration, over
  **per-run mean points** (9 cells × 30 runs = 270 clustered points), cell-level BCa CI.
  **Funnel** iff slope CI < 0; **mix** iff slope CI > 0.
- **H3 (joint, direction-agnostic).** Mechanism **RESOLVED** iff H1 and H2 agree in sign and
  both exclude 0; the *sign* is the finding (funnel vs mix). **Unresolved** if either spans 0.

## 3. Instrument change (the only new code)

Replace the per-seed fresh bridge with a **willing-bridge pool** of size `B` and a fixed
skewed willingness weight vector, under a **new topology factor** so lead-paper cells stay
bit-reproducible:

```
# new assembler branch: topology == "bridge-federated-pool"
weights   = zipf_weights(B, alpha)                 # fixed from the CELL seed; stable per run
idx       = weighted_draw(sha256(f"sor-bridge-pool|{circuit_seed}"), weights)
bridge    = f"bridge#{idx:02d}"                     # B distinct labels, REUSED across circuits
```

- Weights derive from the **cell** seed (not the circuit seed) so the willingness profile is
  fixed within a run and circuits genuinely share bridges → concentration varies.
- Everything else (hop structure, houses, exit-signature grouping, posterior, Miller–Madow H,
  BCa) is **identical to the frozen lead pipeline**.
- Touchpoints: `assembler.py` (new branch + pool helper), `battery.enumerate_cells()` (sweep).
  `confirm_load_rq2.py`, `confirm.py`, `stats.py` are **unchanged**.

## 4. Design matrix (concentration as IV)

Bridge-federated-pool, selector `static`, matched-N, bridge willingness the only manipulation:

- **Pool size** `B ∈ {2, 4, 8}` — 3 levels.
- **Willingness skew** `alpha ∈ {0 (uniform), 1.0 (moderate Zipf), 2.0 (heavy Zipf)}` — 3 levels.
- Full 3×3 = 9 concentration cells (each realizes a distinct mean top-3 concentration).

Run order randomized within cell; deterministic from an ordering seed distinct from data seeds.

## 5. Dependent variables

- **Per-circuit H_i** — Miller–Madow entropy of the uniform posterior over the observation-
  consistent anonymity set (inherited **verbatim** from the frozen lead pipeline).
- **Per-circuit top-3 concentration c_i** — `confirm_load_rq2.bridge_concentration` (unchanged).

## 6. Sampling, seeds, stopping rule

- **R = 30** seeded runs/cell, **C = 50** circuits/run (matched to the lead study).
- Base seed **S0 = 20260719**; per-cell seed = `SHA256(S0 ‖ cell_id ‖ run_index)` (matched).
- **Fixed stopping rule:** all 9 cells × R run to completion. No optional stopping, no interim
  looks. An uninformative cell is reported **inconclusive**, never extended.

## 7. Instrument-validation gate (boolean; blocks the confirmatory run)

> **Re-worded 2026-07-21, pre-freeze (deviation logged in `stage-05-rq2p3-gate-clarification.md`).**
> Items 1–2 were originally written under the naive-funnel prior ("pool reproduces the
> zero-variance degeneracy"; "B=1 → low H"). Both are mechanically wrong under the *ratified*
> posterior and were corrected **before freeze** — see the §7 scope note below. No hypothesis
> changed (H1/H2/H3 in §2 stay two-sided/direction-agnostic); only a mis-specified validation
> gate was fixed. The original dry-pass output that exposed this is cited in the deviation log.

All must pass **before** any confirmatory cell:

1. **Reproduce the lead degeneracy — on the FROZEN branch, not the pool.** The lead
   zero-variance degeneracy is a property of the **injective fresh-bridge map** (a unique
   bridge per circuit seed = effectively no reuse). A finite pool of **any** size `B` draws
   **with replacement**, so birthday collisions make concentration non-constant and ρ defined —
   a pool **cannot and must not** be expected to reproduce the fresh-bridge degeneracy. The
   regression check therefore anchors on the actual frozen `bridge-federated` branch
   (UNTOUCHED): it must still yield **unique exit-signatures → `m_i = 1` → `H_i ≈ 0`, constant
   `c_i = 1/C`**. That is the real "lead reproduces" teeth.
2. **B = 1 boundary.** `B = 1` → all circuits share the one bridge → **`c = 1.0`** (keep this
   concentration tooth). Under the ratified posterior the anonymity set is then **all** circuits
   sharing the exit house, so `H_i` sits at the **HIGH end (maximal mix)** — the "low H" gloss
   was the naive-funnel error and is refuted **by construction** here. Expect high H.
3. **Monotonicity.** Realized mean top-3 concentration is **monotone decreasing in B** and
   **increasing in alpha**, across the sweep, on a dry (non-confirmatory) calibration pass.
4. **Entropy calibration unchanged.** H = log₂N on equiprobable synthetic senders (inherited).

**§7 scope note (why items 1–2 do NOT assert an H-vs-c sign).** This gate validates the
**instrument** — concentration varies monotonically (item 3), entropy is exact (item 4), the
frozen branch is untouched (item 1), and the B=1 boundary hits `c = 1.0` (item 2). It **must not
pre-assert the sign of H-vs-concentration**, because that sign *is* the two-sided confirmatory
question (H1/H2). Baking "expect low H at high concentration" into a validation gate would be
**funnel-circular**; removing it makes the study **more** rigorous, not less. The confirmatory
hypotheses in §2 stay two-sided/direction-agnostic — **UNCHANGED**. (Note: the dry calibration
pass already *previews* a mix, ρ 0→+0.838 across the sweep; this is surfaced openly as an
exploratory preview and does **not** relax the two-sided pre-commitment.)

If any gate item fails → STOP, do not report; surface as NEEDS-OPERATOR.

## 8. Analysis plan

- Effect size + BCa 95% CI for every test; p never reported alone; 10,000 resamples; α = 0.05.
- **H1:** `confirm.rq2_p3_funnel(c, H)` per cell + pooled, but resampled with a **run-level
  cluster bootstrap** (resample whole runs, not individual circuits). Rationale: circuits
  sharing a bridge have identical `c_i` and correlated `H_i`, so per-circuit resampling
  pseudo-replicates and falsely narrows the CI (the same defect noted for lead RQ1-P1). The
  run is the independent unit.
- **H2:** OLS slope of per-run mean-H on per-run mean top-3 concentration (270 clustered
  points); BCa CI resampling **over runs within cells** (cluster bootstrap).
- **Multiplicity:** Holm–Bonferroni over **this study's own family** {H1-pooled, H2-slope}
  (the lead study's family-of-7 is closed and not reopened).
- **Confirmatory vs exploratory:** the 9-cell sweep is confirmatory; any per-cell ρ contrast or
  ΔH replication is labeled EXPLORATORY.
- **Data exclusion (pre-data):** quarantine only on integrity failure (SHA/pcap mismatch,
  non-reproducing seed). No performance-based exclusions.

## 9. Rails (immutable, inherited)

Prereg frozen after approval — never edited (deviations only in a stage-05-style log; no
HARKing; nulls are results). Containment: isolated docker only, self-generated fixture traffic,
lab-only. Budget $0. Worktree only on `feat/sor-consent-relay`. Raw data immutable + SHA-256.

## 10. Freeze block (to complete at approval)

```
FROZEN: 2026-07-21
PREREG SHA-256: recorded in `rq2p3-mechanism-prereg.sha256` (sidecar, full-file sha256sum — same convention as the lead prereg, whose hash lives in `sor-consent-prereg.sha256`; not embedded inline to avoid the self-referential fixpoint)
APPROVED BY: Andre (delegated command authorization 2026-07-21, executed by overseer)
POOL/ SKEW LEVELS LOCKED: B∈{2,4,8}, alpha∈{0,1.0,2.0}
```
