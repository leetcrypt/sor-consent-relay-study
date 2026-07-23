# Stage-08 companion adversarial review (SS5) — red-team of the combined companion paper

**Status: PASS** (self-adversarial pass over the sealed RQ2-P3′ + RQ3 records and the post-seal
filled companion paper). This is an internal integrity red-team, not a new analysis: it computes no
new confirmatory statistic, touches no raw data, and does **not** edit either frozen prereg. It runs
only over already-frozen / already-sealed artifacts:

- Paper under review: `docs/stage-07-companion-methods.md` (RQ2-P3 mechanism + RQ3, D3 combined).
- Sealed records: `output/sor-rq2p3-confirmatory/rq2p3-confirmatory-results.json`
  (SHA-256 `5fdcb379d8a2b88e766748c4907a3754cb34fc1fba56e01e1527fae7c05b872a`);
  `output/sor-rq3-confirmatory/20260722T040640Z/analysis/rq3-confirmatory-analysis.json`
  (SHA-256 `e09c66efe00524ae3e5373bd20121e6e022e6885596f4fa9aabd51653c76929b`), over battery
  `…/confirmatory-data/rq3-battery-results.json` (SHA-256 `5b61e461004722985c1a7a9bc5fdfe855395df3180c71e6efdc3531b8ecf8039`).
- Frozen preregs (recomputed, both **intact / unmoved**): lead `sor-consent-prereg.md` SHA-256
  `f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b`; RQ2-P3 mechanism
  `docs/rq2p3-mechanism-prereg.md` SHA-256 `8db4e8a7ac60f8b2861f2387249db68a3fd44822f6b3d9c7c6990ff65f261a3b`
  (matches sidecar `docs/rq2p3-mechanism-prereg.sha256`).

Three red-team personas were run: (1) METHODOLOGIST, (2) DOMAIN SKEPTIC, (3) REPRODUCIBILITY
AUDITOR. Each check is marked **PASS** / **DEFECT**. One prose-clarity defect was found and fixed
(zero numbers changed); no other defects.

---

## Persona 1 — METHODOLOGIST (statistics & multiplicity)

**M1. Authoritative Holm-7 arithmetic over the frozen size-7 family. PASS.**
Independently reproduced the step-down over the exact frozen family {RQ1-P1, RQ1-P2, RQ2-P1,
RQ2-P3, RQ3-P1-perf, RQ3-P1-latency, RQ3-P2}, `family_size = 7`. Ascending raw p → multipliers
7,6,5,4,3,2,1 give bare products 0, 0, 0, 0.3648, 0.5112, 0.3540, 0.4970; monotone (step-down
running-max) enforcement lifts ranks 6–7 to 0.5112. Adjusted p = {RQ1-P1 0, RQ2-P1 0, RQ2-P3 0,
RQ1-P2 0.365, RQ3-P2 0.511, RQ3-P1-perf 0.511, RQ3-P1-latency 0.511}; survivors @ α = .05 =
{RQ1-P1, RQ2-P1, RQ2-P3}. This reproduces the sealed `authoritative_holm7` rows byte-for-byte.
**Note (prompted the one fix below):** ranks 6–7 report 0.511 even though their bare rank-products
(0.354, 0.497) are smaller — this is Holm monotonicity, not an arithmetic slip; the paper now says
so explicitly.

**M2. "Supersedes partial embedding" claim. PASS.**
The lead paper deliberately assigned its four *reported* tests the largest multipliers (7,6,5,4) —
a conservative partial embedding that can only **over**-correct. The companion's exact Holm-7 ranks
all seven by ascending p. Both are valid; the partial never under-corrects; and the two
already-published lead survivors (RQ1-P1, RQ2-P1) survive under either scheme (their raw p ≈ 0). The
paper states this symmetrically ("both remain valid, the partial never under-corrects") and does not
use the authoritative pass to retroactively weaken a lead claim. No over-claim.

**M3. RQ2-P3 slot integrity (single-slot, mechanism-corrected). PASS.**
The frozen family carries **one** RQ2-P3 slot. The companion fills it with the mechanism-corrected
primary statistic — H1-pooled Spearman ρ, `p_for_holm = 0.0` from the sealed RQ2-P3 record — rather
than the lead's degenerate as-instrumented RQ2-P3 (`p = 1.0`). `family_size` stays 7 (not inflated
to 8 by smuggling in H2). This is the faithful reading of the frozen single-slot design, and the
substitution is disclosed in-paper (§4, §5 Holm bullet, §6) and in the sealed `p_sources`.

**M4. Run-level cluster-bootstrap validity. PASS.**
Both tracks resample the **run** (the confirmatory grouping unit), not the circuit, because circuits
within a run share a bridge draw / churn schedule and are correlated — the same pseudo-replication
defect the lead paper flagged for RQ1-P1. RQ2-P3 H1/H2 use 10,000 BCa run-level resamples; RQ3 uses
a run-level multi-arm bootstrap (independent per-arm resampling + combined leave-one-out jackknife +
BCa endpoints), 10,000 resamples, α = 0.05, verified in the harness to reproduce the frozen
two-sample rule bit-for-bit for the two-mean case. Effect + BCa CI is reported for **every** test.

**M5. Two-sided pre-commitment integrity. PASS.**
RQ2-P3 H1/H2/H3 are pre-registered two-sided (funnel iff CI<0, mix iff CI>0, inconclusive iff spans
0); the mix result is a *positive-side* CI exclusion, not a one-tailed re-test. RQ3-P1-perf /
-latency / -P2 gates are the pre-registered one-sided CI bounds (≥ +10pp, ≤ 100ms, ≤ 0.60) fixed in
the frozen lead prereg — directionality is pre-committed, not chosen post-hoc. p is carried **only**
to order Holm; the CI gates are the decisions, and no bare p is used as a claim anywhere.

**M6. "Effect + CI, never bare p." PASS.** Every reported quantity in §5/§6 leads with a point
estimate and BCa CI; the only p-values shown are the Holm-family adjusted values, explicitly labelled
as ordering/decision inputs.

---

## Persona 2 — DOMAIN SKEPTIC (mechanism & framing)

**D1. Mechanism-correction claim (RQ2-P3 mix qualifies the lead RQ2-P1 shrink as a unique-bridge
artifact). PASS — appropriately scoped.**
The claim is stated as a **qualification/correction**, not an overwrite: the lead RQ2-P1 shrink and
its frozen prereg "stand as published and are not re-litigated." The mechanism (fresh-bridge-per-seed
→ injective exit signatures → set size 1 → H≈0 by construction, removed under a finite shared pool)
is the pre-registered reading in `docs/note-unique-bridge-artifact.md`, tied to the frozen mechanism
prereg SHA. The confirmatory direction (concentration **raises** H; H1 ρ = +0.6244, H2 β = +0.7052,
both CIs strictly positive) matches that mechanism. The skeptic's strongest objection — "you are just
renaming the lead's null" — is met: this is a *new manipulated-IV dose-response* on a *new* pool
topology, not a re-run of RQ2-P1, and the pool cannot reproduce the injective degeneracy (§7 gate 1).

**D2. Mandatory calibration-preview disclosure (dry pass ρ 0 → +0.838). PASS.**
The paper discloses, with equal prominence in §3 and §6, that the offline §7 calibration dry-pass
already previewed the mix direction (Spearman ρ 0 → +0.838 across the sweep; B=1 boundary at high
entropy ≈2.54 bits vs fresh-bridge ≈0.0), so the confirmatory battery "quantifies a dose-response
already visible at calibration," while the pre-committed hypotheses remained two-sided. This is the
honesty discipline the lead paper set. **Auditor cross-check:** the +0.838 figure belongs to the
*synthetic dry calibration pass*, a separate artifact from the confirmatory record; the confirmatory
sealed sweep's per-cell exploratory Spearman tops out at +0.794 (B=8/α=1) and the pooled confirmatory
ρ is +0.6244 — so +0.838 is correctly presented as a *calibration preview*, not mislabelled as a
confirmatory number.

**D3. RQ3 double-null framing. PASS.**
Both RQ3 nulls are reported as findings with equal prominence, not spun:
- **Perf null** is attributed to a *baseline retention ceiling* (every arm heals ~all churn,
  retention ≈ 0.99, margin −0.6pp), i.e. "no headroom," and explicitly says the agent "is not worse …
  merely not better." It does **not** re-frame a null as a win.
- **Latency** correctly holds the ≤100ms budget (−13.5ms, CI upper 34.9ms) and the paper is careful
  that P1 fails on the *perf* gate, not latency.
- **P2 non-exclusion** is framed as a **power** limitation at n = 30 ("underpowered to exclude a small
  rebuild-timing signal … rather than a false all-clear"), never as "no fingerprint exists."
This is the correct, non-spun reading of AUC 0.587 with CI upper 0.703 > 0.60.

**D4. Calibration-vs-confirmatory AUC separation (no HARKing). PASS — explicitly verified.**
The §3-4 calibration AUC ≈ **0.93** is *churned(kp30)-vs-low-churn(kp5) regime* discrimination on
labelled control signals; the confirmatory RQ3-P2 AUC = **0.587** is *agent-vs-pooled-baseline-selector*
discrimination on the confirmatory cells. The paper keeps these **distinct** in both §5 (parenthetical
disclosure: "a different comparison … the calibration validated the instrument and does not preview
the confirmatory selector value") and the sealed `honest_disclosure`. The frozen detector
(`rebuild_classifier_auc`, per-run mean inter-rebuild-gap) is the same instrument in both, not tuned to
confirmatory data — no HARKing, no detector-to-data fitting.

**D5. Nulls / mix reported as results, with equal prominence. PASS.** The abstract, §5, and §6 all
carry the double-null and the mix with the same weight as any positive finding; scope & limitations
(§6) bound both to the lab grid.

---

## Persona 3 — REPRODUCIBILITY AUDITOR (number fidelity & provenance)

**R1. Number fidelity, RQ2-P3 (paper ⟷ `rq2p3-confirmatory-results.json`). PASS.**
- H1 pooled Spearman ρ point **+0.6244**, CI **[+0.5941, +0.6545]** ⟷ sealed 0.624397 /
  [0.594080, 0.654513]. ✓
- H2 OLS slope β **+0.7052**, CI **[+0.6195, +0.7903]**, n = 270 ⟷ 0.705250 / [0.619455, 0.790277] /
  n_points 270. ✓
- H3 RESOLVED = MIX (agree_in_sign ∧ both_exclude_zero). ✓ Holm own-family {H1,H2} both reject. ✓
- Sweep exemplars: B=2/α=0 conc ≈1.00, H ≈2.54 ⟷ 1.0000 / 2.5410; B=8/α=0 conc ≈0.51, H ≈2.19 ⟷
  0.5053 / 2.1870. ✓ Grid metadata C=50, R=30, 9 cells, 13,500 bridged circuits, S0=20260719,
  10,000 resamples. ✓

**R2. Number fidelity, RQ3 (paper ⟷ `rq3-confirmatory-analysis.json`). PASS.**
- RQ3-P1-perf point **−0.6pp**, CI **[−1.58pp, +0.39pp]**, gate lower ≥ +10pp → **fails** ⟷
  −0.006312 / [−0.015830, +0.003866], holds=false. ✓
- RQ3-P1-latency point **−13.5ms**, CI **[−52.1, +34.9]ms**, min-baseline = **random**, ≤100ms →
  **holds** ⟷ −13.4916 / [−52.1484, +34.9112], min_latency_baseline_arm="random", holds=true. ✓
- RQ3-P2 AUC **0.587**, CI **[0.458, 0.703]**, upper 0.703 > 0.60 → **fails** (n_agent 30 /
  n_baseline 60) ⟷ 0.586944 / [0.458056, 0.703436], holds=false. ✓
- RQ3-P3 = **H0** (p1_holds=false ∧ p2_holds=false). ✓
- Holm-7 rows / survivors / non-survivors reproduce the sealed `authoritative_holm7` (see M1). ✓

**R3. Ollama temp-0 cross-hardware caveat. PASS.**
The paper states, with equal prominence to the RQ1 timing caveat (§4 and §6-scope-(iii)), that the
agent (`qwen2.5:3b`, local Ollama, temperature 0) is **not bit-identical across machines**
(quantization / GPU logit drift) and is reproducible via the **committed decision-log + (seed,
state-hash) cache replay**, *not* via independent model re-execution on other hardware. This matches
the sealed `honest_disclosure` verbatim in substance.

**R4. Prereg SHAs intact. PASS.** Recomputed on disk: lead `f22331a72e…` and RQ2-P3 `8db4e8a7…`
both match their pinned values and the sidecar; neither prereg file was edited by this review or by
the fills. The sealed record digests `5fdcb379…`, `e09c66ef…`, `5b61e461…` all recompute exactly.

**R5. Blinding integrity — Results filled once, post-seal. PASS.**
Git history: scaffold authored blind (`4f89a90`); a prose-only QA fix (`50b1701`); RQ2-P3
Results/Discussion filled **after** its battery sealed (`e0d865d`, following `f920516` STEP-2 seal);
RQ3 Results/Discussion filled **after** the RQ3 seal (`1b6449b`, following `47faee3`). Each track's
Results were filled **once**, from its sealed record, with no pre-seal fill and no re-slice/re-fill.
Consistent with the un-blinded header and §5/§6 provenance notes.

**R6. Containment framing. PASS.** RQ2-P3 ran offline + deterministic ($0, no engine/traffic/grid);
RQ3 ran operator-GO'd on the isolated docker grid (`live-docker-e2e`, self-generated fixture
traffic), agent arm local/open-weight ($0, frontier arm inert). The paper's framing is
defensive-measurement throughout; no containment line is crossed or implied.

---

## Defect found and corrected (1)

- **Holm-7 monotonicity read as a possible arithmetic slip (prose clarity).** In §5 the three RQ3
  non-survivors are listed as RQ3-P2 (rank 5 ×3, 0.511), RQ3-P1-perf (rank 6 ×2, 0.511),
  RQ3-P1-latency (rank 7 ×1, 0.511). A reader recomputing the bare rank-products would get 0.354
  (rank 6) and 0.497 (rank 7), not 0.511 — the reported values are the **step-down monotone-enforced**
  Holm adjusted p (a later rank never reports a smaller adjusted p than an earlier one), which is
  correct but was unexplained. Added a one-clause parenthetical stating the monotonicity so the values
  cannot be mistaken for an error. **No number changed** — the 0.511 values are the Holm-correct
  outputs and were already faithful to the sealed record; only an explanatory clause was added.

## Residual honest limitations (carried, not defects)

- **RQ3-P2 is underpowered (n = 30 runs/arm)** to exclude a small rebuild-timing fingerprint; the
  non-exclusion is a power limitation, reported as such, not a proof of a fingerprint nor a false
  all-clear. Carried openly in §5/§6.
- **RQ3 perf null is grid-bound**: it follows from a baseline retention ceiling under the pinned
  churn (kp30/steps20) on this small grid, not a general claim that adaptive selection cannot help.
- **RQ2-P3 mix is an as-instrumented concentration effect** on the ratified exit-signature posterior,
  not an internet-scale claim.
- **Agent-arm reproducibility** is via committed decision-log + cache replay, not cross-hardware model
  re-execution (Ollama temp-0 drift) — stated with equal prominence to the RQ1 timing caveat.

**Outcome:** the combined companion paper is internally consistent, number-faithful to both sealed
records, spin-free (both nulls and the mix reported with equal prominence), multiplicity-correct
(authoritative Holm-7 reproduced independently), and blinding-honest (each track filled once,
post-seal), after the one monotonicity-clarity prose fix. Both frozen preregs are intact. Ready for
operator review.
