# Companion Methods (BLIND scaffold): The Unique-Bridge / Mix Mechanism (RQ2-P3) and Churn-Resilient Agent Selection (RQ3)

**Draft — companion methods. Both tracks have cleared their human gates (RQ2-P3 freeze; RQ3 operator-GO); Results/Discussion are UN-BLINDED and filled from the sealed records only.**

> **Paper-structure note (deliberately left OPEN).** Whether this material ships as a second
> standalone paper, as extension sections folded into the lead paper
> (`docs/stage-07-paper-draft.md`), or as a short mechanism note is an **operator editorial
> decision** and is **not** pre-committed here. The two methods tracks below are therefore
> written as **self-contained sections** that can be lifted into either structure.
>
> **Blinding & gating status (binding).**
> - **RQ2-P3 mechanism study — FROZEN + SEALED; its Results/Discussion are now UN-BLINDED below.**
>   The prereg (`docs/rq2p3-mechanism-prereg.md`, own slug `sor-consent-rq2p3`) was **frozen
>   2026-07-21** (§10 signed; full-file SHA-256 `8db4e8a7ac60f8b2861f2387249db68a3fd44822f6b3d9c7c6990ff65f261a3b`
>   in the sidecar `docs/rq2p3-mechanism-prereg.sha256`). The confirmatory battery then ran
>   **offline + deterministic** and its record is **sealed** (`output/sor-rq2p3-confirmatory/…`,
>   results SHA-256 `5fdcb379d8a2…`). §5/§6 for RQ2-P3 are filled **from that sealed record only**,
>   the same post-seal discipline the lead paper used.
> - **RQ3 companion — RUN + UN-BLINDED.** Hypotheses, gates, and analysis are **frozen** in the lead
>   prereg (`sor-consent-prereg.md`, SHA-256
>   `f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b`, §3/§4/§6); the two open
>   `[APPROVAL]` execution params were pinned blind in `docs/rq3-companion-run-brief.md`. The
>   confirmatory battery ran **operator-GO'd on the live isolated docker grid** (3 arms × R=30 ×
>   C=50 = 4,500 real circuits, `live-docker-e2e`) and its record is **sealed**
>   (`output/sor-rq3-confirmatory/…`, battery SHA-256 `5b61e461…`, analysis SHA-256 `e09c66ef…`).
>   §5/§6 for RQ3 are filled **from that sealed record only**.
> - **All Results / Discussion below are now UN-BLINDED, filled from the sealed records only.** Both
>   tracks have cleared their human gates (RQ2-P3 freeze; RQ3 operator-GO); the **authoritative
>   Holm-7** over the frozen size-7 family is computed. The frozen lead prereg is authoritative and
>   **unedited**; the lead RQ1/RQ2-P1 findings are not re-litigated.

---

## Abstract *(both tracks UN-BLINDED — confirmatory findings folded in from the sealed records)*

The lead study measured a consent-gated, federated, nested-SSH relay instrument and reported two
honest non-confirmations: no measurable entry↔exit linkability leak (RQ1) and a Holm-significant
**shrink** of the per-circuit anonymity set under federation (RQ2-P1). This companion pursues the
two questions the lead paper could not close. **First (RQ2-P3′, a mechanism study):** the lead
"shrink" may be an **instrument artifact** — the bridge-federated topology assigns a *fresh*
willing bridge per circuit seed, so every adversary-observable exit signature is unique, every
anonymity set collapses to size 1, and entropy is driven to ≈0 by construction rather than by
funnelling. We re-instrument the willing-bridge layer as a **finite shared pool** with skewed
willingness and treat bridge **concentration as a manipulated independent variable** (a 3×3
dose-response over pool size and skew), asking **two-sided** whether concentration *reduces*
(funnel) or *raises* (mix) the anonymity set. **Second (RQ3, churn resilience):** we measure
whether a **local open-weight agent** path-selector (`qwen2.5:3b`) retains throughput and adds
tolerable latency under a pinned churn schedule, without leaving a classifiable **rebuild
fingerprint**. Both tracks are pre-registered, detector-frozen, and calibration-gated before any
confirmatory cell. *(Confirmatory findings, now un-blinded: **RQ2-P3 resolves MIX** —
shared-pool concentration raises the anonymity set, correcting the lead "shrink" as a
unique-bridge artifact; **RQ3 is a null on both counts** — on this grid every selector
heals ~all churn (no +10 pp agent margin) and the rebuild-timing fingerprint cannot be
excluded at n=30. The authoritative Holm-7 leaves RQ1-P1, RQ2-P1, and RQ2-P3 surviving.)*

---

## 1. Introduction (deltas beyond the lead paper)

The lead paper (G4 + RQ1 + RQ2) established the consent-gate instrument and reported its
linkability and anonymity-set readings. Two threads there were *raised but not resolved*, and this
companion is scoped to exactly those.

**(a) The unique-bridge / mix mechanism.** The lead RQ2-P1 result — federation **shrinks** the
anonymity set (ΔH < 0) — was reported honestly, but the lead paper also flagged its RQ2-P3
mechanism test as **degenerate as-instrumented**: the bridge-federated arm assigns a fresh bridge
per circuit seed, so top-3 bridge concentration is a constant `c_i = 1/C` with **zero variance**
and Spearman ρ is undefined. The mechanistic reading (developed in
`docs/note-unique-bridge-artifact.md`) is that the adversary's observable is an
`exit_signature = (exit_house, bridge_label)`; a unique bridge per circuit makes every signature
unique, so the observation-consistent anonymity set is size 1 and H≈0 **by injective construction,
not by funnelling**. If that is right, a *finite shared* bridge pool should make circuits share
signatures, enlarge the anonymity set, and act as a **mix** (concentration *raises* H) — the
**opposite** of the naive funnel intuition. This makes RQ2-P3′ a test of whether the lead
"shrink" headline is a unique-bridge artifact that a mechanism study can qualify or correct. This
mix reading connects the consent-gate bridge to the classical mix [Chaum1981] and to
information-theoretic set metrics [Serjantov2002; Diaz2002] the lead paper already adopts.

**(b) Churn-resilient agent selection.** The lead paper held the selector at `static`; RQ3 asks
whether an **adaptive** selector improves resilience when the relay pool churns. Two costs bound
any such gain and are the confirmatory tension: (i) rebuilding a circuit after a dropped hop adds
latency and can erode throughput, and (ii) the *timing pattern* of rebuilds is itself a
side-channel — a rebuild-event classifier could fingerprint the selector, echoing website- and
flow-fingerprinting results on onion transports [SirinamIJW18; RahmanSMGW20] and the
rebuild/timing-classifier spirit of CLASI [Barton2025], and compounding statistical-disclosure
exposure over repeated circuits [Danezis2003]. RQ3 therefore pairs a **performance** gate with an
**anonymity** (non-fingerprint) gate: an agent selector only "helps" if it retains throughput at
tolerable added latency **and** its rebuild pattern is not classifiable.

## 2. Related work (deltas)

The lead paper's Related Work (onion routing / SOR [Egners2012], flow correlation
[NasrBH18; OhYMH22], anonymity metrics [Serjantov2002; Diaz2002], social-trust G4 neighbours) is
inherited unchanged. The companion adds two narrow deltas, citing **only** already-grounded
references:

- **Bridge-as-mix vs. bridge-as-funnel.** Concentrating flows through few willing bridges can be
  read either as a funnel (fewer distinct observation classes → smaller sets) or as a mix
  [Chaum1981] (shared observation class → larger sets). The set-size effect is quantified with the
  same entropy metrics the lead paper uses [Serjantov2002; Diaz2002]; the companion's contribution
  is a **manipulated-concentration dose-response** that adjudicates the sign, not a new estimator.
- **Rebuild-timing as a fingerprint.** Churn-driven circuit rebuilds create a timing series an
  adversary may classify; this is the fingerprinting/timing lineage [SirinamIJW18; RahmanSMGW20;
  Barton2025] applied to *selector-induced* rebuild events rather than page loads. The companion
  adopts a **frozen, fixture-calibrated** rebuild classifier and reads its AUC as an instrument
  reading, mirroring the lead paper's frozen-correlator discipline (no correlator/classifier
  state-of-the-art is claimed).

---

## 3. Methods A — RQ2-P3′ funnelling-mechanism study **[FROZEN 2026-07-21 — prereg §10 signed]**

> **This section describes a study whose prereg (`docs/rq2p3-mechanism-prereg.md`) is FROZEN.**
> Design and parameters were operator-approved and locked; the **human freeze checkpoint** (§10
> signed 2026-07-21, full-file SHA-256 `8db4e8a7ac60f8b2861f2387249db68a3fd44822f6b3d9c7c6990ff65f261a3b`
> in the sidecar `docs/rq2p3-mechanism-prereg.sha256`) is complete. The confirmatory battery then
> ran **offline + deterministic** and its record is **sealed** (results SHA-256 `5fdcb379d8a2…`).
> Everything below is the pre-registered *plan* exactly as frozen; the §5/§6 numbers are read
> **from that sealed record only**.

**Design (manipulated-IV dose-response).** A new assembler topology, `bridge-federated-pool`,
replaces the fresh-per-seed bridge with a **finite willing-bridge pool** of size `B` under a fixed
Zipf willingness skew `alpha`: `weights = zipf_weights(B, alpha)` derived from the **cell** seed
(so the willingness profile is fixed within a run), and each circuit draws
`idx = weighted_draw(sha256("sor-bridge-pool|{circuit_seed}"), weights)` → `bridge#{idx:02d}`,
a label **reused** across circuits so concentration genuinely varies. Everything downstream (hop
structure, houses, exit-signature grouping, Miller–Madow entropy, BCa bootstrap) is **identical**
to the frozen lead pipeline; the lead `bridge-federated` branch is **untouched and bit-reproducible**.
The manipulation grid is **B ∈ {2, 4, 8} × alpha ∈ {0 (uniform), 1.0, 2.0}** = 9 concentration
cells; run order randomized within cell from an ordering seed distinct from the data seeds.

**Hypotheses (two-sided; direction not presumed).**
- **H1 (within-cell association).** Spearman ρ between per-circuit top-3 willing-bridge
  concentration `c_i` and per-circuit entropy `H_i`. **Funnel** iff BCa 95% CI < 0; **mix** iff CI
  > 0; **inconclusive** iff CI spans 0.
- **H2 (dose-response).** OLS slope β of per-run mean-H on per-run mean top-3 concentration over
  9 cells × 30 runs = 270 clustered points; cell-level BCa CI; funnel iff slope CI < 0, mix iff CI > 0.
- **H3 (joint, direction-agnostic).** Mechanism **RESOLVED** iff H1 and H2 agree in sign and both
  exclude 0 — the *sign* (funnel vs mix) is the finding; **unresolved** if either spans 0.

**Dependent variables.** Per-circuit `H_i` (Miller–Madow entropy of the uniform posterior over the
observation-consistent anonymity set, inherited verbatim) and per-circuit top-3 concentration `c_i`
(`confirm_load_rq2.bridge_concentration`, unchanged).

**Sampling.** R = 30 seeded runs/cell, C = 50 circuits/run (matched to the lead study); base seed
S0 = 20260719, per-cell seed `SHA256(S0 ‖ cell_id ‖ run_index)`; fixed stopping rule (all 9 cells ×
R to completion; uninformative cell → inconclusive; no optional stopping).

**Analysis.** Effect size + BCa 95% CI (10,000 resamples, α = 0.05) for every test; **run-level
cluster bootstrap** (resample whole runs, not circuits) because circuits sharing a bridge have
identical `c_i` and correlated `H_i` — the same pseudo-replication defect the lead paper flagged
for RQ1-P1. Holm–Bonferroni over **this study's own family** {H1-pooled, H2-slope}; the lead
family-of-7 is closed and **not** reopened here. Any per-cell ρ contrast or ΔH replication is
labelled **EXPLORATORY**, never a re-run of the frozen RQ2-P1.

**Instrument-validation gate (§7, re-worded pre-freeze — cite
`docs/stage-05-rq2p3-gate-clarification.md`).** The §7 items were **re-worded before freeze**
because the original items 1–2 encoded the naive-funnel prior and were mechanically wrong under the
ratified posterior (transparent deviation logged; no hypothesis changed — H1/H2/H3 stay two-sided).
The re-worded gate validates the **instrument**, not a sign:
1. the **frozen** `bridge-federated` branch (not the pool) still shows the lead degeneracy — unique
   signatures → `m_i = 1` → `H_i ≈ 0`, constant `c_i = 1/C` (a pool draws with replacement and
   *cannot* reproduce the injective fresh-bridge degeneracy, so the regression teeth live on the
   untouched branch);
2. the **B = 1 boundary** yields `c = 1.0` (concentration tooth) **and**, under the ratified
   posterior, `H` at the **high** end (maximal mix) — the naive "low H" gloss is refuted by
   construction;
3. realized mean top-3 concentration is **monotone** (decreasing in B, increasing in alpha);
4. entropy calibration inherited (H = log₂N on equiprobable synthetic senders).
A **§7 scope note** records that the gate **must not** pre-assert the H-vs-concentration sign —
that sign *is* the two-sided confirmatory question; baking it in would be funnel-circular.

**Pre-registered calibration finding (NOT a confirmatory result).** The dry §7 pass — synthetic,
offline, no confirmatory record read — already **previews a mix**: across the sweep Spearman ρ runs
from ≈0 up to **+0.838** (all cells ρ ≥ 0), the B = 1 boundary sits at high entropy (≈2.54 bits vs
the fresh-bridge reference ≈0.0), and monotonicity + entropy calibration pass. This is surfaced
**openly as a pre-registered calibration preview**, per the §7 scope note; it does **not** relax the
two-sided pre-commitment, and the confirmatory sign remains withheld until after freeze. Honest
disclosure the eventual write-up must carry: because the dry pass already previews the mix
direction, the confirmatory battery **quantifies a dose-response already visible at calibration**;
the two-sided pre-commitment stands and the lead RQ2-P1 headline is not re-litigated.

## 4. Methods B — RQ3 churn-resilient agent selector (frozen prereg)

> Hypotheses, gates, DVs, and analysis are **frozen** in `sor-consent-prereg.md` (§3/§4/§6) and are
> restated, not redefined. The two open `[APPROVAL]` execution params were pinned **blind** to RQ3
> outcomes (`docs/rq3-companion-run-brief.md` §2).

**Design.** Selector strategy {`static`, `random`, `agent`} at the RQ3 control cell
(single-house / bridge-off) under a pinned churn schedule; `static` is the interleaved control, and
control runs are bracketed before and after the {`random`, `agent`} treatments to catch grid drift.
The cells are enumerated **separately** from the frozen 6-cell lead lattice so the lead battery
stays bit-reproducible.

**Pinned execution parameters (blind).**
- **Agent = `qwen2.5:3b`** via local Ollama (`agent_selector.OllamaAgentPolicy`, temperature 0,
  per-run seed, `(seed, state-hash)` decision cache, deterministic heuristic fallback on query
  failure). Local / open-weight, **$0**; the Claude/frontier arm (`ClaudeExploratoryPolicy`) stays
  **inert / EXPLORATORY / budget-gated** and is not wired.
- **Reproducibility caveat (accepted; must be stated in the paper).** Ollama at temperature 0 is
  **not bit-identical across machines** (quantization / GPU logit drift). The agent arm is
  reproducible via the **committed decision-log + `(seed, state-hash)` cache replay**, *not* via
  independent model re-execution on other hardware — the same honesty class as the RQ1 timing
  caveat. The decision log + cache are committed as the reproducibility anchor.
- **Churn = `kill_prob_pct = 30`, `steps = 20`**, one deterministic schedule per run seeded from
  the same `SHA256(S0 ‖ cell ‖ run)` family; low-churn calibration baseline `kill_prob_pct = 5`.

**Dependent variables (frozen).** Throughput retention (throughput under churn / no-churn
baseline); added latency = median end-to-end latency(agent) − median latency(best baseline arm), in
ms — a **live** measurement only; and rebuild-classifier AUC over the rebuild-event time series (the
per-run mean inter-rebuild-gap signal), per the [Barton2025] CLASI spirit.

**Confirmatory gates (frozen, family-of-7).**

| Test | Frozen gate |
|---|---|
| RQ3-P1-perf | throughput-retention(agent) − max(static, random): 95% CI lower bound **≥ 10 pp** |
| RQ3-P1-latency | added-latency(agent): 95% CI upper bound **≤ 100 ms** |
| RQ3-P2 | rebuild-classifier AUC: 95% CI upper bound **≤ 0.60** |
| RQ3-P3 | logical AND: **CONFIRM** iff P1 ∧ P2 (perf gain *without* a rebuild fingerprint); else H0 |

R = 30 runs/cell, C = 50 circuits/run, fixed stopping rule (inherited unchanged).

**Analysis + multiplicity (Holm-7 supersedes note).** The three RQ3 tests were always in the
frozen size-7 family {RQ1-P1, RQ1-P2, RQ2-P1, RQ2-P3, RQ3-P1-perf, RQ3-P1-latency, RQ3-P2}. Once
all seven p-values exist, the companion computes the **exact Holm-7** step-down over the whole
family; this is the **authoritative** final correction and **supersedes** the lead paper's
deliberately conservative *partial* embedding (7/6/5/4 report-4) — both remain valid, the partial
never under-corrects, and the lead paper's already-published RQ1-P1 / RQ2-P1 survive regardless
(their reported raw p ≈ 0 — a lead-paper result, not a companion figure). Effect size + BCa 95% CI
for every test; nulls reported honestly (a selector that does **not** beat baselines, or a rebuild
pattern that **is** classifiable, is the finding). The QUIC / `ssh3` transport arm stays
**EXPLORATORY and deferred** (design decision D3), never in the Holm family.

**Calibration gates (already green; NOT confirmatory results).** Two boolean gates block the RQ3
confirmatory battery and have both passed on a **dry, synthetic, offline** pass:
- **Churn-bites** — at the pinned `kp = 30 / steps = 20` the churn genuinely bites (non-zero
  drops/rebuilds across every RQ3 cell), so the retention and classifier tests are not degenerate.
- **Rebuild-classifier calibration** — churned (`kp = 30`) vs low-churn baseline (`kp = 5`) is
  **separable** on the per-run mean inter-rebuild-gap signal (calibration AUC ≈ **0.93**), while
  baseline-vs-baseline is **not** (null AUC ≈ **0.52**); plus an agent cache-replay reproducibility
  check and the inherited entropy calibration. These are **calibration** readings on labelled
  control signals, **not fit to confirmatory cells**; the frozen instrument
  (`rebuild_interval_gaps`, `rebuild_classifier_auc`) is unchanged.

---

## 5. Results *(both tracks UN-BLINDED — filled from the sealed records only)*

- **RQ2-P3′ (H1 / H2 / H3) — RESOLVED: MIX.** From the sealed confirmatory record (9 cells × R=30 ×
  C=50, offline + deterministic, S0 = 20260719):
  - **H1 (within-cell association).** Pooled Spearman **ρ = +0.6244**, BCa 95% CI **[+0.5941, +0.6545]**
    (run-level cluster bootstrap, 10,000 resamples). CI excludes 0 on the **positive** side → **mix**.
  - **H2 (dose-response).** OLS slope of per-run mean-H on per-run mean concentration
    **β = +0.7052**, BCa 95% CI **[+0.6195, +0.7903]** over n = 270 run-level points. CI positive →
    **mix**.
  - **H3 (joint).** H1 and H2 **agree in sign (both +)** and **both exclude 0** → mechanism
    **RESOLVED = MIX**.
  - **Holm (own family {H1-pooled, H2-slope}, size 2).** Both tests **reject** at α = 0.05 after
    Holm correction. *(p carried only for Holm ordering; the effect + CI above are the reported
    quantities — never a bare p.)*
  - Across the sweep, as pool size B rises concentration falls **and** entropy H falls together
    (e.g. B=2/α=0: conc ≈ 1.00, H ≈ 2.54; B=8/α=0: conc ≈ 0.51, H ≈ 2.19) — concentration and H move
    **together, positively**: higher concentration ⇒ higher anonymity (mix), not lower (funnel).
- **RQ3-P1-perf / RQ3-P1-latency / RQ3-P2 / RQ3-P3 — H0 (honest null).** From the sealed live
  battery (3 selector arms × R=30 × C=50 = 4,500 real isolated-docker circuits, `measured_from =
  live-docker-e2e`; agent = `qwen2.5:3b` local Ollama; run-level multi-arm bootstrap, 10,000 BCa
  resamples, α = 0.05; results SHA-256 `e09c66ef…`):
  - **RQ3-P1-perf — FAILS the +10 pp gate.** Throughput-retention margin = retention(agent) −
    max(static, random) = **−0.6 pp**, BCa 95% CI **[−1.58 pp, +0.39 pp]**. Every selector heals
    ~all churn drops (mean retention ≈ 0.99 across arms), so the agent shows **no** ≥ +10 pp gain.
  - **RQ3-P1-latency — WITHIN the ≤ 100 ms budget.** Added-latency(agent) = median e2e
    latency(agent) − median latency(min-latency baseline = random) = **−13.5 ms**, BCa 95% CI
    **[−52.1, +34.9] ms**; CI upper 34.9 ms ≤ 100 ms — the agent is **not** slower than the best
    baseline (the perf gate, not latency, is what fails P1).
  - **RQ3-P2 — FAILS the ≤ 0.60 ceiling (fingerprint not excluded).** Rebuild-classifier AUC (agent
    per-run mean inter-rebuild-gap vs. the pooled baseline selectors) = **0.587**, BCa 95% CI
    **[0.458, 0.703]**; CI upper 0.703 **> 0.60**, so a rebuild-timing fingerprint of the agent
    **cannot be ruled out** at the pre-registered bar (the test is underpowered at n = 30 runs/arm).
    *(Disclosure: the green §3-4 **calibration** gate reported AUC ≈ 0.93 — but that was
    **churned-vs-low-churn regime** discrimination on labelled control signals, a **different**
    comparison from this confirmatory **agent-vs-baseline-selector** AUC of 0.587; the calibration
    validated the instrument and does **not** preview the confirmatory selector value.)*
  - **RQ3-P3 (joint) — H0.** P1 fails (perf) **and** P2 fails → the agent selector is **not**
    confirmed to help without a fingerprint. Reported as the finding, not spun.
- **Holm-7 (companion, authoritative).** Over the frozen size-7 family {RQ1-P1, RQ1-P2, RQ2-P1,
  RQ2-P3, RQ3-P1-perf, RQ3-P1-latency, RQ3-P2}, exact Holm step-down (the RQ2-P3 slot carries the
  **mechanism-corrected** primary H1-pooled Spearman p, superseding the lead's degenerate
  as-instrumented RQ2-P3): **survivors = RQ1-P1 (rank 1 ×7), RQ2-P1 shrink (rank 2 ×6), RQ2-P3 mix
  (rank 3 ×5)** — all adjusted p = 0. **Do not survive:** RQ1-P2 (rank 4 ×4, adj p = 0.365), RQ3-P2
  (rank 5 ×3, 0.511), RQ3-P1-perf (rank 6 ×2, 0.511), RQ3-P1-latency (rank 7 ×1, 0.511). *(Holm
  adjusted p-values are step-down **monotone-enforced** — a later rank never reports a smaller
  adjusted p than an earlier one — so ranks 6–7 inherit the rank-5 value rather than their smaller
  bare rank-products; this is standard Holm, not an arithmetic slip.)* This is the
  **authoritative** final correction and **supersedes** the lead paper's conservative *partial*
  embedding (report-4); both remain valid, the partial never under-corrects, and lead RQ1-P1 /
  RQ2-P1 survive regardless.

## 6. Discussion *(both tracks UN-BLINDED)*

- **Does a shared bridge funnel or mix? — It mixes.** Both pre-registered two-sided tests resolve
  **positive** (H1 ρ = +0.6244 CI [+0.5941, +0.6545]; H2 β = +0.7052 CI [+0.6195, +0.7903]; H3
  RESOLVED = mix; Holm both reject). Plainly: **concentrating circuits through a finite shared
  willing-bridge pool RAISES the per-circuit anonymity set** — circuits that share a bridge share an
  exit signature, so the observation-consistent set grows and entropy rises. This **refutes the naive
  funnel intuition** (that concentration would shrink the set) and, per the mechanism developed in
  `docs/note-unique-bridge-artifact.md`, **qualifies the lead RQ2-P1 "shrink" as a unique-bridge
  (fresh-bridge-per-circuit) instrument artifact**: the lead topology assigned a *fresh* bridge per
  circuit seed, making every exit signature unique, every anonymity set size 1, and H≈0 by injective
  construction rather than by funnelling. Under a finite shared pool the injectivity is removed and
  the true sign of the concentration→anonymity relationship is revealed to be a **mix**. This is an
  honest **qualification/correction** of the lead reading via the frozen mechanism prereg (SHA-256
  `8db4e8a7ac60f8b2861f2387249db68a3fd44822f6b3d9c7c6990ff65f261a3b`), **not** an overwrite: the lead
  RQ2-P1 result and its frozen prereg stand as published and are not re-litigated.
  - **Mandatory disclosure (pre-registration honesty).** The §7 calibration dry-pass — synthetic,
    offline, no confirmatory record read — **already previewed this direction** (Spearman ρ running
    0 → +0.838 across the sweep, B=1 boundary at high entropy). The confirmatory battery therefore
    **quantifies a dose-response that was already visible at calibration**; the pre-committed
    hypotheses were nonetheless **two-sided** and that pre-commitment is unchanged. We surface the
    calibration preview openly so no reader mistakes the confirmatory sign for a post-hoc choice.
- **Does the agent selector help without leaking? — No (H0), on both counts.** RQ3-P3 requires the
  agent to clear the +10 pp retention / ≤ 100 ms latency bar **and** leave a non-classifiable
  rebuild pattern (AUC CI upper ≤ 0.60); it does neither decisively. On **performance**, the honest
  reason is that churn at kp = 30 / steps = 20 is **fully healed by every arm** — static, random,
  and the agent all rebuild ~all dropped hops (retention ≈ 0.99), so there is simply **no headroom**
  for an adaptive selector to win the +10 pp margin (margin −0.6 pp, CI [−1.58, +0.39] pp). The
  agent is not *worse* — added-latency is within budget (−13.5 ms, CI upper 34.9 ms ≤ 100 ms) — it
  is merely **not better**, because the baseline is already at the retention ceiling on this grid.
  On **anonymity**, the rebuild-timing classifier reaches AUC 0.587 with CI upper 0.703 > 0.60, so
  the pre-registered bar to certify "no usable fingerprint" is **not met**: at n = 30 runs/arm the
  test is **underpowered** to exclude a small rebuild-timing signal, and we report that limitation
  rather than a false all-clear. The honest reading: **on this lab grid the local open-weight agent
  selector neither beats the baselines nor is demonstrably fingerprint-free** — a null on both P1
  and P2, exactly the outcome the design pre-committed to publish with equal prominence.
- **Authoritative multiplicity (Holm-7).** With all seven pre-registered p-values now in hand, the
  companion's exact Holm-7 supersedes the lead paper's conservative partial embedding (operator
  decision D3). Three hypotheses survive: **RQ1-P1** (below-chance linkability AUC — no usable
  entry↔exit leak), **RQ2-P1** (federation *shrinks* the anonymity set, the lead headline null),
  and **RQ2-P3** (shared-pool concentration *mixes* — the mechanism correction). The four that do
  not survive are RQ1-P2 (padding efficacy), and all three RQ3 tests — consistent with the RQ3 H0
  above. Note the RQ2-P3 slot now carries the **mechanism-corrected** primary statistic (H1-pooled
  Spearman, adj p = 0) rather than the lead's degenerate as-instrumented RQ2-P3 (adj p = 1): the
  companion's frozen-detector method both *caught* the unique-bridge artifact and *promotes* the
  corrected mechanism finding into the surviving family. Lead RQ1-P1 and RQ2-P1 survive regardless.
- **Scope & limitations.** Both findings are scoped to the lab grid (1-house / bridge-off control,
  single-laptop isolated-docker, two non-forwarding phones, self-generated fixture traffic) and inherit the lead paper's external-validity
  caveats. Specific to this companion: (i) the RQ2-P3 mix is an **as-instrumented** concentration
  effect on the ratified exit-signature posterior, not an internet-scale claim; (ii) the RQ3 nulls
  are **grid-bound** — the perf null follows from a baseline retention ceiling under the pinned
  churn, and the P2 non-exclusion is an n = 30 **power** limitation, not a proof of a fingerprint;
  (iii) the agent arm carries the accepted **reproducibility caveat** (Ollama temp-0 is reproducible
  via the committed decision-log + (seed, state-hash) cache replay, *not* via cross-hardware model
  re-execution), stated with equal prominence to the RQ1 timing caveat.

---

## References

Inherit the lead paper's reference list (`docs/stage-07-paper-draft.md` §References) unchanged. The
companion cites only references already grounded in the frozen sources: **Chaum1981, Serjantov2002,
Diaz2002, Egners2012, NasrBH18, OhYMH22, SirinamIJW18, RahmanSMGW20, Danezis2003** are in the lead
paper's list; **Barton2025** (CLASI rebuild/timing-classifier spirit) is grounded in the frozen
lead prereg's RQ3 dependent-variable definition (`sor-consent-prereg.md` §3) and carries into the
companion's assembled list. No reference is added that cannot be grounded from the frozen prereg or
stage-01 literature.
