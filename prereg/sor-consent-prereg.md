# Pre-registration — sor-consent (FROZEN)

> **STATUS: FROZEN — human-approved at the stage-03 checkpoint on 2026-07-19.**
> The SHA-256 of this file is recorded in `sor-consent-prereg.sha256` and must be echoed into
> every run manifest (R2). Every item previously marked **[APPROVAL]** is hereby **approved as
> stated**. From here, **no change edits this file** — any deviation appears only in stage 05's
> `sor-consent-deviations.md` (§8). No confirmatory data-collecting run may occur until the
> instrument-validation gate (§5) passes green. Per `shared/GOAL-sor-consent.md` the prereg freeze
> (now done) and any containment-boundary change are the human gates; the paid frontier-model
> selector arm is **off the confirmatory path** (decision D1, §9 — the agent arm runs on a local
> model at $0) and only re-engages the budget gate if run as an EXPLORATORY contrast.

## 1. Study information

- **Title:** Consent-Gated Federated Onion Routing: Linkability, Anonymity Set, and
  Churn Resilience of an In-Band Accept/Reject Relay Model
- **Slug:** sor-consent · **Draft date:** 2026-07-19 · **Author:** operator + Claude (sci-method pipeline)
- **Hypotheses:** normative in `../../02-hypothesis/output/sor-consent-hypothesis.md`
  §H-RQ1, §H-RQ2, §H-RQ3 (each H1/H0, predictions P1–P3, falsification condition, operational
  definitions, scope). That file is authoritative; no rewording here. Reproduced references
  below point to it by section, not by copy.
- **Build dependency:** every DV is gated behind `shared/roadmap-sor-consent.md` items
  R1–R7 [REQUIRED-for-H1]. hack-house has no data plane today; the instrument is built in the
  worktree `/home/dell/coding/learning/hack-house-sor-consent` (branch `feat/sor-consent-relay`)
  before any confirmatory run. sci-method and hack-house `main` are never modified.

## 2. Design

- **Type:** Confirmatory factorial controlled comparison (systems measurement / simulation),
  three RQ families sharing one instrument, each with its own control arm. Traffic is
  self-generated to our own fixtures; measurement is on our own lab grid only.
- **Justification vs alternatives:**
  - *Analytical modelling alone* (e.g., entropy bounds from a graph model) cannot capture the
    consent-gating funnel effect or a real nested-SSH rebuild fingerprint — the phenomena under
    test are emergent from the actual data plane, so a built instrument is required.
  - *Single-factor A/B per RQ* would miss cross-factor interactions (e.g., topology × selector)
    and force three separate underpowered studies; a shared factorial instrument amortizes the
    (large) build cost across all three DV families.
  - *Internet-scale / live-network measurement* is out of scope and out of the containment
    envelope; the claim is deliberately scoped to the local grid (§7 External).
- **Design matrix (confirmatory cells):**
  - **RQ1 (linkability):** bridge {off, on, on+padding} — 3 levels.
  - **RQ2 (anonymity set):** topology {1-house-N, bridge-federated, directory-federated} at
    **matched total node count N** — 3 levels.
  - **RQ3 (churn resilience):** selector {static, random, agent} × churn schedule {seeded set,
    §4} — 3 selector levels.
  - Full crossing is **not** run; cells are organized per RQ with the other factors held at
    their declared control (RQ1 at single-house/static; RQ2 at bridge-off/static; RQ3 at
    single-house/bridge-off). **N/A cells are declared here, not dropped ad hoc:** padding is
    only defined for bridge-on (bridge-off+padding is N/A). **The `agent` selector runs on a
    pinned local/open-weight model from the hackhouse agent fabric (decided 2026-07-19, §Design
    decisions), so RQ3 is confirmatory at $0 with no paid-budget gate;** a paid frontier model is
    an optional EXPLORATORY "stronger-model" contrast only. If the local model fails the §5
    latency/quality calibration, RQ3's agent arm falls back to a funded follow-on — a data-driven
    fallback at the gate, not a pre-commitment.
- **Assignment / order:** materials are fixed (no unit randomization); **run order is
  randomized within each cell and controls are interleaved with treatments** (control arm of
  each RQ scheduled before and after its treatments) so calibration drift on the grid is caught.
  All stochastic elements are seed-controlled (§4, R1).
- **Blinding:** the correlator/entropy/classifier code (R7) is written and calibrated on the
  instrument-validation fixtures (§5) — known-linked/known-unlinked control pairs and
  equiprobable-sender synthetic sets — **before any confirmatory cell is run**; no per-cell
  tuning of any detector is permitted (deviations policy §8). No human inspects confirmatory
  intermediate results before the full battery completes.

## 3. Variables

- **Independent variables (levels → how manipulated):**
  - *Bridge condition* {off, on, on+padding} — R6 bridge mode + R1/R4 padding config.
  - *Federation topology* {1-house-N, bridge-federated, directory-federated} — R6 federation.
  - *Selector strategy* {static, random, agent} — R7 selector module; `agent` = **local/open-weight
    model** from the hackhouse agent fabric, **[APPROVAL]** exact model ID + weights digest pinned
    at freeze; confirmatory, no paid-budget gate (§Design decisions, 2026-07-19).
  - *Churn schedule* — seeded VM spin/kill schedule over the hackhouse VM fabric (R7 churn, R1 seed).
  - *(EXPLORATORY — decided 2026-07-19, §Design decisions)* transport arm {TCP-nested,
    QUIC-nested `ssh3`} — R1/R4. **TCP-nested is the confirmatory workhorse; QUIC stays
    EXPLORATORY** (orthogonal to all three RQs; a weak lit-gap; avoids doubling cells + build).
    Labeled EXPLORATORY in analysis and paper.
- **Dependent variables (exact metric → measurement procedure):**
  - **RQ1 — correlation AUC:** area under the ROC of the R7 flow-correlation detector (inherited
    from hh-agents R8/R10) scoring (entry-segment, exit-segment) pairs as same/different circuit.
    Computed from `bridge_forward` byte/latency events (R3) at the bridge node. 95% CI by
    bootstrap over circuit pairs.
  - **RQ2 — anonymity-set entropy H:** Shannon entropy of the adversary's posterior over
    candidate senders per circuit; effective set size S = 2^H per [Serjantov2002], normalized
    d = H/log2(N) per [Diaz2002]. **Estimator [APPROVAL]:** plug-in (MLE) entropy with
    **Miller–Madow bias correction** for finite-sample bias; 95% CI by bootstrap over circuits.
    ΔH = H(federated) − H(single-house, matched N).
  - **RQ3 — throughput retention, added latency, rebuild-classifier AUC:** throughput retention =
    (throughput under churn) / (no-churn baseline throughput), per selector; added latency =
    median end-to-end latency(selector) − median latency(best baseline), in ms; rebuild-classifier
    AUC = AUC of the R7 classifier on the rebuild-event time series (per [Barton2025] CLASI
    spirit). All from R3 event logs + R4 per-hop byte/latency events.
- **Confounds → strategy:**
  | Confound | Strategy |
  |---|---|
  | Background load / thermal throttling on grid devices (2 phones + laptop) | RANDOMIZE run order + interleave controls; MEASURE per-device idle baseline each session; report as covariate |
  | Device heterogeneity (phone vs laptop hop capacity) | HOLD CONSTANT — node-role→device mapping fixed across all cells of a comparison; documented in manifest (R2) |
  | Detector overfitting / tuning contamination | ELIMINATE — detectors frozen + calibrated on §5 fixtures pre-battery; no per-cell retuning (blinding, §2) |
  | Seed leakage / non-determinism | ELIMINATE — single base seed → per-cell derived seeds in config; R1 determinism acceptance check |
  | Wall-clock timestamps entering the correlator | HOLD CONSTANT — detector consumes only R3 event features declared at freeze; wall-clock excluded from features |
  | Self-generated traffic ≠ real user traffic | ACCEPT (construct) — scoped in §7; fixtures documented and versioned |
  | Isolation escape (forwarder on host) | ELIMINATE — `assert engine != local` or refuse (R4; `bridge.py:528-529`); containment gate §5 |
  | Small number of houses/nodes for RQ2 entropy | MEASURE + ACCEPT — node counts reported; underpowered-for-large-N caveat → Limitations |

## 4. Sampling & power

- **Unit of analysis:** RQ1 — the (entry, exit) circuit-segment pair (AUC over the pair set);
  RQ2 — the circuit (entropy of the per-circuit sender posterior); RQ3 — the seeded run
  (throughput/latency aggregate) and the rebuild event (classifier).
- **Repetition count [APPROVAL]:** **R = 30 independent seeded runs per design cell**; each run
  builds a fixed **C = 50 circuits** (→ ≥ 50 same-circuit and ≥ 50 different-circuit pairs per
  run for RQ1, ≥ 1500 pairs/cell). Rationale is a **precision target**, not a formal power
  analysis: with ≥ 1500 scored pairs per cell the bootstrap 95% CI half-width on AUC is
  expected ≤ 0.03, sufficient to resolve the RQ1 floor (§6) away from 0.5; 30 runs satisfies the
  CLT/dispersion requirement in `_config/rigor-standards.md §Statistics` for stochastic systems.
  Exact R, C confirmed at freeze against the §5 calibration CI widths.
- **Seeds:** one base seed **`S0 = 20260719`** (fixed at freeze; the freeze date, no hidden
  structure); per-cell seed = `SHA256(S0 ‖ cell_id ‖ run_index)` truncated to u64, echoed into
  every `manifest.json` (R2) and
  `events.jsonl` (R3). Determinism verified by R1's acceptance check on a spot-checked cell.
- **Stopping rule (fixed, pre-registered):** all cells × R runs are run to completion; **no
  optional stopping, no peeking-driven extension, no interim looks.** If a cell's CI is
  uninformative at the frozen R, that cell is reported **inconclusive** — the battery is not
  extended to chase significance (`rigor-standards §Statistics`; GOAL Phase T).

## 5. Materials & procedure

- **Instrument (built, worktree):** R1–R7 in `hack-house-sor-consent` @ branch
  `feat/sor-consent-relay`; git SHA recorded per run (R2). Components: seed plumbing (R1),
  provenance writer (R2), immutable JSONL event log + SHA-256 (R3), nested-SSH data plane (R4),
  consent handshake + X25519 hop credentials (R5), federation/bridge (R6), churn generator +
  selector + correlator/entropy/classifier (R7).
- **Compute grid:** 2 Android phones + laptop as nested-SSH relay hops (SSH); hackhouse VM
  fabric as churn source. Node-role→device mapping pinned per comparison and recorded in R2.
- **Isolation / containment (binding at every cell):** every forwarder runs in an **isolated
  engine only** (docker/multipass via `bridge.py:517-530`); **`assert engine != local` or the
  run refuses.** All traffic is **self-generated to our own fixtures**, lab-only across our own
  houses/VMs. No external target, no live-network relay — a hard stop requiring explicit human
  approval (GOAL envelope (b)). Fixtures (payload streams, synthetic sender sets) versioned in
  the worktree and checksummed.
- **Models:** static/random selectors need no model — **RQ1 and RQ2 use no selector model at all**
  (selector held at `static` for their controls), so the lead paper (G4+RQ1+RQ2) is fully pinned by
  this freeze. The `agent` selector arm (RQ3 only) uses a **single pinned local/open-weight model**
  served from the hackhouse agent fabric. **Bounded instrument-pin (the one value not nameable at
  freeze):** the exact model ID + weights digest + sampling params (temperature, top_p, max tokens)
  are fixed at the **§5 RQ3 calibration gate — before any RQ3 confirmatory run — recorded in the
  run manifest (R2), and immutable for the entire RQ3 battery;** any change is a §8 deviation. This
  bound touches RQ3 alone and never RQ1/RQ2. This supersedes the roadmap's "frontier-model arm"
  assumption: choosing a local model
  **eliminates** the paid-frontier budget gate (GOAL envelope (c)) rather than bypassing it, and
  improves reproducibility (pinned weights vs a moving hosted endpoint). A paid frontier model, if
  ever run, is an EXPLORATORY contrast, separately budget-gated. The arm's prompt text is versioned
  and included in the paper appendix (`rigor-standards §LLM/agent`).
- **Instrument-validation HARD GATE (must pass before ANY confirmatory run; boolean, from
  GOAL "Done" and roadmap Phase IV — each maps to an R-item acceptance check):**
  1. **End-to-end delivery:** a 3-hop self-traffic circuit across the grid delivers a known
     payload end-to-end; each hop's pcap exists and checksums (R4).
  2. **Seeded reproducibility:** `smoke-e2e.sh`-style bringup is reproducible from a seed —
     same seed + same churn script → identical circuit-build sequence and selector choices,
     diff-clean modulo wall-clock (R1).
  3. **Correlator calibration (= P3-RQ1):** the R7 correlator scores a known-linked control
     pair at AUC ≈ 1 and a known-unlinked pair at AUC ≈ 0.5.
  4. **Entropy calibration (= P2-RQ2):** the estimator returns H = log2(N) (within MC error)
     for N equiprobable synthetic senders.
  5. **Isolation:** forwarders confirmed isolated engine only — `assert engine != local` or
     refuse (R4; `bridge.py:528-529`).
  6. **Provenance integrity:** replaying a fixture circuit yields a schema-valid `events.jsonl`
     whose SHA-256 matches `manifest.json`; log is append-only (R2/R3).
  Gate is boolean; any red → back to the failing R-item; **no confirmatory cell runs until all
  green** (GOAL; roadmap Phase IV).
- **Procedure (numbered; becomes the stage-04/05 run spec):**
  1. Build R1–R7; pass every [REQUIRED-for-H1] acceptance check as a test where feasible.
  2. Run the §5 instrument-validation gate; record the gate report.
  3. Freeze seeds + thresholds (this document, on approval) and hash.
  4. Run the confirmatory battery: all §2 cells × R runs, controls interleaved, order randomized
     within cell. Each run writes `manifest.json` (R2), appends `events.jsonl` (R3), writes
     per-hop `pcap/hop<N>.pcap` (R4) — all SHA-256'd and immutable.
  5. R7 analysis reads `events.jsonl` + pcaps → `metrics.json` (AUC, H, throughput/latency,
     rebuild AUC) per cell.
  6. Lock raw outputs (stage 05 immutability). No edits; cleaning only in analysis code on copies.

## 6. Analysis plan

Effect size + 95% CI reported for **every** comparison (`rigor-standards §Statistics`);
p-values never reported alone. All confirmatory tests below; anything else EXPLORATORY.

- **RQ1 (H-RQ1 P1, P2):**
  - *P1 (leak):* bridge-on correlation AUC with bootstrap 95% CI. **Confirmation gate = the CI
    excludes 0.5** (a leak is present); **NULL/refute** if the CI includes 0.5. This mirrors the
    stage-02 falsification condition exactly and removes a dead zone (see below). Materiality is a
    **separate pre-registered label, not the gate:** AUC CI-lower-bound ≥ **0.60 [APPROVAL]** ⇒
    "material leak"; between 0.5 and 0.60 ⇒ "weak-but-real leak." Raw AUC + CI are reported in
    every case. *(Refines the stage-02 P1 operationalization pre-data — legitimate, not HARKing:
    the original "AUC > AUC_floor AND CI excludes 0.5" created an un-adjudicable zone where a real
    leak, e.g. AUC 0.57 / CI [0.53, 0.61], was neither confirmable nor refutable; §Design decisions.)*
  - *P2 (padding efficacy):* ΔAUC = AUC(bridge-on, no-pad) − AUC(bridge-on, +pad); paired
    bootstrap 95% CI. Padding effective iff ΔAUC CI **> 0**.
- **RQ2 (H-RQ2 P1, P3):**
  - *P1 (two-sided):* ΔH = H(federated) − H(single-house, matched N), bootstrap 95% CI;
    **the design does not presume the sign.** **CONFIRM-grow** if ΔH CI **> 0**;
    **CONFIRM-shrink (honest null, published with equal prominence)** if ΔH CI **< 0**;
    **inconclusive** if the CI spans 0. *Matched-N rule [APPROVAL]:* single-house arm sized so
    its node count equals the **total consenting nodes** of the federated arm.
  - *P3 (mechanism, confirmatory):* Spearman ρ between top-k bridge concentration (fraction of
    circuits through the top-k willing bridges) and per-circuit H, with 95% CI; negative ρ
    quantifies funneling. **k = 3 [APPROVAL].**
- **RQ3 (H-RQ3 P1, P2, joint P3):**
  - *P1 (perf):* throughput_retention(agent) − max(static, random), bootstrap 95% CI, plus
    added-latency(agent) 95% CI. Perf holds iff retention-margin CI lower bound **≥ X%** AND
    added-latency CI upper bound **≤ Y ms**. **X = 10 percentage points; Y = 100 ms [APPROVAL]**
    (grid is a LAN of phones+laptop; Y is the added-latency budget over the best baseline; both
    reconfirmed against §5 baseline latencies at freeze).
  - *P2 (anonymity):* rebuild-classifier AUC with 95% CI. Anonymity holds iff the CI **upper
    bound ≤ AUC_ceiling**. **AUC_ceiling = 0.60 [APPROVAL]** (symmetric with the RQ1 floor:
    a rebuild pattern discriminable at ≤ 0.60 is not a usable fingerprint).
  - *P3 (joint):* **CONFIRM** iff P1 AND P2 both hold; **H0** if either fails.
- **Multiple-comparison correction [APPROVAL]:** the confirmatory hypothesis tests across all
  three RQ families are corrected together by **Holm–Bonferroni** (`rigor-standards §Statistics`
  default). Test family (7 confirmatory tests): {RQ1-P1, RQ1-P2, RQ2-P1, RQ2-P3, RQ3-P1-perf,
  RQ3-P1-latency, RQ3-P2}. RQ3-P3 is a logical AND of already-corrected tests, not a new test.
  CIs are reported at the Holm-adjusted level for the confirmatory family. EXPLORATORY results
  (transport arm; any post-hoc contrast) are labeled and excluded from the confirmatory column.
- **Assumption checks + fallbacks:** all inference is **bootstrap/permutation-based** and
  therefore assumption-light by construction; no normality assumed. Bootstrap: 10,000 resamples,
  BCa intervals; seed spot-check (3 seeds must agree to MC error). Entropy bias handled by
  Miller–Madow (§3); sensitivity to a second estimator (NSB) reported EXPLORATORY.
- **Data exclusion rules (pre-data):** a cell/run is quarantined (logged, never silently
  dropped) **only** if its data-integrity check fails — `events.jsonl` SHA-256 ≠ manifest, a
  pcap fails checksum, an in-place edit is detected, or the seed does not reproduce the logged
  circuit-build sequence for that spot-checked cell. No performance-based exclusions.
- **Outcome mapping (decision rule, frozen now; thresholds frozen on approval):**
  - RQ1: P1 confirm ⇒ bridge linkability leak (motivates the padding artifact); P1 null ⇒
    headline null (bridge present, no measurable leak — reportable). P2 sign gives padding efficacy.
  - RQ2: ΔH CI > 0 ⇒ federation grows the anonymity set; ΔH CI < 0 ⇒ **honest null / shrink,
    reported as prominently as growth**; spans 0 ⇒ inconclusive. Expectation-bias guard binding
    (`rigor-standards`; GOAL honest-expectation).
  - RQ3: P1 ∧ P2 ⇒ agent selector helps without a rebuild fingerprint; either fails ⇒ H0
    (perf gain cancelled by teardown overhead, or rebuild timing is classifiable).

## 7. Threats to validity

| Threat | Type | Disposition |
|---|---|---|
| Background load / thermal throttling skews throughput & latency | Internal | MITIGATED — randomized order, interleaved controls, per-session idle baseline measured & modelled |
| Detector tuning contamination (correlator/classifier fit to confirmatory data) | Internal | ELIMINATED — detectors frozen + calibrated on §5 fixtures pre-battery; no per-cell retuning |
| Device heterogeneity confounds topology/selector effects | Internal | HOLD CONSTANT — node-role→device mapping pinned per comparison, recorded in R2 manifest |
| Local grid (2 phones + laptop, few houses) ≠ internet-scale; not a global passive adversary | External | ACCEPTED + scoped — claims restricted to the tested topology/scale → Limitations |
| Self-generated fixture traffic ≠ real user traffic patterns | Construct | ACCEPTED — inherent to a lab measurement; scoped → Limitations; fixtures versioned |
| A single detector's AUC as "linkability"; plug-in H as "anonymity" | Construct | MITIGATED — calibrated instruments (§5 P3/P2 gates); H reported with S=2^H and normalized d; second estimator (NSB) as EXPLORATORY sensitivity |
| Multiplicity across three RQ families | Statistical | Holm–Bonferroni over the 7 confirmatory tests (§6); EXPLORATORY family labeled |
| Small node/house counts → wide entropy CIs | Statistical | ACCEPTED + reported — node counts stated; underpowered-for-large-N caveat → Limitations |
| Bootstrap CI validity at small per-cell N | Statistical | MITIGATED — R=30 runs × C=50 circuits (§4); BCa intervals; seed spot-check |
| Agent-arm model non-determinism (temp>0) | Statistical | R repeated runs; variance reported; model ID + params pinned (§5) |
| Isolation escape / traffic leaving the lab | Internal/containment | ELIMINATED — `assert engine != local` or refuse; self-fixtures only; external target = human-gated hard stop |
| Dual-use of an onion-routing data plane | Construct/ethics | Defensive-measurement framing load-bearing; containment (scout §6) binding; stage-08 red-teams the framing |

**Citation-integrity notes (carried forward):** [Stutzbach2006] session-count figures are
**secondary-sourced** — re-confirm against the primary before any load-bearing use in the paper;
[Constantinides2026] is a **Feb-2026 preprint** — re-confirm status/claims before citing as
support. Neither is load-bearing for any confirmatory threshold above.

## 8. Freeze block (ACTIVE)

- **Freeze date: 2026-07-19** (human-approved at the stage-03 checkpoint). **SHA-256:** recorded
  in `sor-consent-prereg.sha256` (external, so this file's own hash is well-defined) and echoed
  into every run manifest (R2). All [APPROVAL] values (§4/§6 thresholds, base seed S0, matched-N,
  top-k, X%, Y ms, ceilings, estimator, R and C, Holm family) are **approved as stated**. The one
  bounded post-freeze pin — the RQ3 local agent-model ID/digest — is fixed at the §5 calibration
  gate before any RQ3 confirmatory run and recorded immutably (§5); it does not affect RQ1/RQ2.
- **Frozen on approval:** the three RQ hypotheses (by reference to the stage-02 file); all IV
  levels (§2–3); all DV operationalizations (§3, R7 metrics); the numeric thresholds now marked
  [APPROVAL] — RQ1 confirmation gate (CI excludes 0.5) + the 0.60 materiality label, matched-N
  rule, top-k, X%, Y ms, AUC_ceiling, entropy estimator, local agent-model ID + weights digest,
  base seed S0, R and C; the Holm confirmatory family (§6); and the stopping rule (§4).
- **Reporting/packaging (frozen intent, not a statistical commitment):** all three RQs are
  pre-registered as confirmatory now; the **lead paper = G4 + RQ1 + RQ2**; **RQ3 is a designated
  severable follow-on** (§Design decisions). Packaging is finalized at stage 07 from the results;
  the shared prereg + Holm family are disclosed in whichever papers result.
- **Post-freeze policy:** any change of any kind — including promoting the transport arm or the
  paid frontier selector arm — appears **only** in stage 05's `sor-consent-deviations.md` with
  reason and expected impact; the frozen file is never edited. No HARKing; confirmatory ≠ exploratory.
- **Attestation at freeze:** detectors (correlator, entropy estimator, rebuild classifier) were
  calibrated only on the §5 instrument-validation fixtures, with no exposure to confirmatory-cell
  data, before the battery.

## 9. Design decisions (pre-freeze, 2026-07-19)

Recorded so the human approver and stage-08 reviewer can audit the reasoning and **circle back**
if any assumption changes. All predate any confirmatory data. Full rationale +
rejected-alternatives in `sor-consent-design-notes.md`.

| # | Fork | Decision | Why |
|---|---|---|---|
| D1 | Agent selector: paid frontier vs {static,random} only | **Local/open-weight model** from hackhouse fabric; confirmatory, $0 | Answers RQ3's actual question; eliminates (not bypasses) the paid-budget gate; better reproducibility than a hosted endpoint. Fallback: funded follow-on only if it fails §5 calibration |
| D2 | RQ1 confirmation gate | **Gate = CI excludes 0.5**; 0.60 becomes a materiality *label* | Removes an un-adjudicable dead zone (real leak that was neither confirmable nor refutable); mirrors the stage-02 falsification condition |
| D3 | Transport arm (TCP vs QUIC/ssh3) | **TCP-nested confirmatory; QUIC EXPLORATORY** | Orthogonal to all three RQs; a weak lit-gap; avoids doubling cells, build, and multiplicity |
| D4 | Containment boundary | **Unchanged, verbatim** | Isolated-engine-only / self-fixtures / lab-only is the dual-use ethical backbone; no reason to touch |
| D5 | Freeze/hash | **Deferred** — remains DRAFT until explicit human "freeze" | Operator wants the packaging fork (D6) kept open to circle back before committing |

### D6 — Packaging fork: one paper vs several (the explicit "circle-back" record)

- **The fork:** bundle all three RQs into one paper, or split per-RQ into several.
- **Structure of the evidence:** RQ1 (bridge linkability) and RQ2 (federation's anonymity-set
  effect) are two halves of **one** story — the anonymity properties of the consent-gated federated
  topology, measured with the same anonymity metrics for the same reader. RQ3 (churn resilience +
  agent-managed rebuilds) is a **different axis** (availability / AI-network-control) with a
  different reviewer pool. Natural fracture line = **RQ1+RQ2 | RQ3**. Three papers = over-fragmented
  (RQ1 alone is thin, and salami-slicing RQ1 from RQ2 is unjustifiable).
- **Decision (revisable at stage 07):** **Lead paper = G4 + RQ1 + RQ2; RQ3 = designated severable
  follow-on.** Matches roadmap Phase P (2026-07-19), now on firmer footing because D1 makes RQ3 a
  $0 confirmatory arm rather than a budget-fragile one.
- **Why this is safe to defer:** the packaging choice lives at **stage 07 (drafting)**, not here.
  We **build once** (R1–R7), **pre-register all three RQs as confirmatory now**, **run the battery
  once**, and only *then* decide packaging from the observed results. Deferring costs nothing and is
  **not** salami-slicing: they are one pre-registered instrument + battery, and the shared prereg +
  Holm-corrected family are disclosed in whichever papers result (which is *more* rigorous). The
  only property this preserves that dropping RQ3 would forfeit is RQ3's confirmatory eligibility.
- **Circle-back triggers:** revisit at stage 07 if — RQ3's results are strong enough to headline on
  their own (→ firm split), or thin enough to fold in as a section (→ single bundled paper); or if a
  target venue's scope forces a particular cut. Record any change in the stage-05 deviations log if
  it touches a frozen item, otherwise as a stage-07 drafting note.
