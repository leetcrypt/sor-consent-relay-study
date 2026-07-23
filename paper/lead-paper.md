# Consent-Gated Federated Onion Routing: Linkability and Anonymity-Set Effects of an In-Band Accept/Reject Relay Model

**Draft — SS4 lead paper (G4 + RQ1 + RQ2). Results/Discussion filled from the frozen §6 pass.**

> **Blinding status (prereg §2, binding).** Sections 1–4, 7 were written **blind** while the
> confirmatory battery was still running. Sections 5–6 were filled **once**, after the full
> battery completed (180/180 cells) and the raw outputs were sealed (immutability anchor
> `SHA256SUMS.txt`), from the **single** frozen §6 inferential pass
> (`docs/stage-06-analysis.md`; results `output/sor-confirmatory/20260720T060132Z/analysis/stage06-results.json`).
> No number was inspected before that seal. The frozen prereg
> (`sor-consent-prereg.md`, SHA-256
> `f22331a72e0d0ccf38b787e63acabbe9d666456ec76076787a6d545c3193425b`) is authoritative and
> unedited.
>
> **RQ2 posterior (ratified).** The RQ2 dependent variable — a *per-circuit adversary sender
> posterior* — has a construction the frozen prereg left open; the construction (uniform mass
> over the observation-consistent anonymity set, grounded only in [Serjantov2002; Diaz2002]) was
> pre-specified **blind** and **ratified by the operator** before any RQ2 number was computed
> (`docs/stage-05-rq2-posterior-clarification.md`, **RATIFIED**). It is recomputable offline from
> the sealed per-circuit seeds.
>
> **Headline (honest null/negative).** Neither hoped-for effect is confirmed. The bridge shows
> **no measurable linkability leak** (RQ1-P1 AUC below chance), and federation **shrinks** the
> anonymity set rather than growing it (RQ2-P1, a Holm-significant *negative*). We report this
> plainly — nulls and negatives are results.

---

## Abstract *(skeleton — quantitative claims held until data + RQ2 ratification)*

Onion-routing systems typically admit any relay that meets a directory's technical criteria;
they do not model **relay consent** — a host's in-band, per-circuit choice to carry a given
flow. We build and measure a **consent-gated, federated, nested-SSH relay data plane** in which
every hop must explicitly accept or reject each circuit through a signed in-band handshake
(Ed25519-authenticated, X25519 per-hop credentials), and in which relays are organized into
**houses** that federate either through a shared **bridge** or through a **directory**. Treating
this as a *measurement instrument* for a trust model's exposure (not a service that provides
anonymity), we ask two confirmatory questions on a single-laptop isolated-docker grid: **(RQ1)**
does a shared bridge introduce a measurable flow-linkability leak between a circuit's entry and
exit segments, and does cover padding remove it; **(RQ2)** does federating relays across houses
**grow or shrink** the anonymity set an adversary faces, and is any effect explained by
**bridge-concentration funnelling**. All detectors are frozen and calibrated on
known-linked/known-unlinked and equiprobable-sender fixtures before any confirmatory cell is run;
all inference is bootstrap-based with BCa 95% CIs, Holm–Bonferroni-corrected across the
confirmatory family. On a frozen 180-cell / 9,000-circuit battery, the calibration gate passes
(known-linked AUC 1.00, known-unlinked 0.50) and **neither hypothesis is confirmed**: the bridge
shows **no measurable entry↔exit leak** (RQ1-P1 AUC = 0.466, 95% CI [0.452, 0.480], *below*
chance), so padding has nothing to suppress (RQ1-P2 ΔAUC = +0.011, CI [−0.002, +0.023],
Holm-adjusted p = 0.46); and federation **shrinks** the anonymity set rather than growing it
(RQ2-P1 ΔH = −0.96 bits, CI [−1.06, −0.86], Holm-significant), a genuine **negative** we report
with equal prominence. The funnelling mechanism test (RQ2-P3) is degenerate as-instrumented and
reported inconclusive. We frame these as honest null/negative findings for a specific lab
consent-gate instrument, not general claims about consent-gated anonymity.

---

## 1. Introduction

Anonymous-communication systems from onion routing [Reed1997; Dingledine2004] to its SSH-based
descendant SOR [Egners2012] share a membership model that is essentially *permissionless at the
relay*: a node participates if it meets directory or protocol criteria, and the routing layer
does not represent whether a host **consents** to carry a particular circuit. Yet in
social-trust and friend-to-friend designs — Freenet [Clarke2000], membership-concealing overlays
[Vasserman2009], and social-graph routers such as Pisces [Mittal2012] and X-Vine [Mittal2012b] —
*who is willing to relay for whom* is a first-class property. No existing system, to our
knowledge, makes **per-circuit relay consent an in-band, cryptographically-authenticated protocol
step** and then **measures the privacy consequences** of that gate. That gap — an
accept/reject relay model whose linkability and anonymity-set behaviour are empirically
characterised — is the novelty this work targets (**G4**).

We do not propose consent-gating as a deployed anonymity service. We build it as a
**defensive-measurement instrument**: a controlled data plane whose knobs (bridge on/off, cover
padding, federation topology) let us *measure* how a consent gate reshapes an adversary's view.
Two consequences of the gate are non-obvious and testable:

1. **A shared bridge is a linkability hazard (RQ1).** When federated houses route through one
   shared bridge node, that node observes both the entry and exit segments of circuits crossing
   it. Modern flow-correlation attacks link such segments at high accuracy from timing/volume
   alone [NasrBH18; OhYMH22; RahmanSMGW20]. We ask whether our bridge exhibits a **measurable**
   entry↔exit correlation leak, and whether **cover padding** closes it.

2. **Consent-gating can funnel, not just spread (RQ2).** Federation intuitively enlarges the
   candidate-sender set and thus anonymity [Serjantov2002; Diaz2002]. But a consent gate means
   only *willing* relays carry traffic; if willingness concentrates on a few bridges, circuits
   funnel through them and the effective anonymity set may **shrink**. We therefore treat the
   sign of the federation effect as **unknown a priori** and report a shrink as prominently as a
   growth.

**Contributions.** (i) The design and instrument-grade implementation of a consent-gated,
federated, nested-SSH relay data plane with signed in-band accept/reject and per-hop X25519
credentials (§3, §4). (ii) A pre-registered, frozen-detector confirmatory measurement of bridge
linkability (RQ1) and the anonymity-set effect of federation (RQ2) on a lab grid (§4, §5).
(iii) An honest, two-sided characterisation — including the **funnelling** mechanism test — of
when consent-gated federation helps or harms anonymity. **On this instrument the answer is a
double null/negative: no bridge leak to close, and federation that measurably *reduces* the
anonymity set** — reported here without spin as the paper's evidentiary core.

**Scope.** Claims are deliberately restricted to the tested lab topology and scale (a single laptop's isolated-docker containers; few houses); this is not an internet-scale or global-passive-adversary result (§7).
The paired **churn-resilience** question (RQ3) and a QUIC/`ssh3` transport arm [Michel2023] are
pre-registered but held for a companion paper; this lead paper covers G4 + RQ1 + RQ2 only.

---

## 2. Related work

**Onion routing and SSH-based relays.** Mixes and onion routing originate with Chaum [Chaum1981]
and Reed–Syverson–Goldschlag [Reed1997], with Tor [Dingledine2004] as the dominant deployment.
SOR [Egners2012] is the **direct prior art**: it layers onion routing over stock SSH tunnels,
which is exactly our transport substrate. Nesting SSH inside SSH raises the well-known
TCP-over-TCP throughput/latency pathology [Honda2005], motivating our latency-aware measurement
and a (exploratory) QUIC-based `ssh3` transport [Michel2023]; UDP-based latency work on onion
services [AlAzad2023] is complementary. **None of these model per-circuit relay consent**, which
is the axis we add and measure.

**Flow correlation / linkability (RQ1).** That an adversary seeing two segments of a flow can
link them is established: low-cost traffic analysis [MurdochD05], realistic-adversary correlation
on Tor [JohnsonWJSS13], and deep-learning correlators DeepCorr [NasrBH18] and DeepCoFFEA
[OhYMH22] achieve high linking accuracy; packet-timing (Tik-Tok [RahmanSMGW20]) and deep
fingerprinting [SirinamIJW18] show timing/volume suffice. We do **not** advance correlator
state-of-the-art; we adopt a **frozen, fixture-calibrated** correlator (calibration gate §5) and
use its AUC purely as an *instrument reading* of whether our bridge leaks — the contribution is
the consent-gate/bridge measurement, not the attack.

**Anonymity metrics and Sybil/directory concerns (RQ2).** We quantify anonymity with the
information-theoretic set metrics of Serjantov–Danezis [Serjantov2002] (entropy of the adversary
posterior; effective set size S = 2^H) and Díaz et al. [Diaz2002] (normalized degree
d = H/log₂N). Federation across mutually-distrusting houses evokes decentralised-directory and
Sybil questions [Douceur2002; Winter2016] and statistical-disclosure exposure over repeated
circuits [Danezis2003]. Our **matched-N** design isolates the *topology* effect (federated vs.
single-house at equal total node count) rather than a node-count artifact.

**Social-trust / consent-adjacent designs (G4 neighbours).** The closest neighbours treat
relaying willingness or social linkage as structural: Freenet's friend-to-friend mode
[Clarke2000], membership-concealing overlays [Vasserman2009], Drac's social low-volume comms
[Danezis2010], and social-graph routers Pisces [Mittal2012] / X-Vine [Mittal2012b] / STor
[Zhou2011]. These encode *trust in the graph*; **none makes consent an in-band, per-circuit,
signed accept/reject protocol step whose linkability and anonymity-set consequences are then
measured** — the specific gap G4 fills.

---

## 3. System design (the instrument)

The instrument is a nested-SSH relay data plane built into an existing zero-knowledge chat relay
(hack-house), entirely within an isolated worktree. It has seven components (roadmap R1–R7); the
subset load-bearing for this lead paper (RQ1 + RQ2, `static` selector, no model) is fully pinned
by the freeze. Key mechanisms:

- **Consent handshake (R5).** Each hop receives a signed in-band consent *request* and must
  **accept or reject** before it will carry the circuit. Requests are **Ed25519-signed** by the
  originating persona and **verified before acceptance**; an unsigned or forged request is
  rejected. Per-hop credentials are **X25519-sealed to the host's public key**, so a hop
  credential decrypts *only* with that host's private key (no shared-symmetric secret).
- **Nested-SSH circuits (R4).** A circuit is a chain of SSH tunnels across grid hops; the entry
  and exit **segments** are the observable units for RQ1. Every hop's traffic is captured to an
  immutable per-hop pcap, written once and checksummed.
- **Federation / bridge (R6).** Relays are grouped into **houses**. Houses federate via a shared
  **bridge** node or via a **directory**; a circuit's federation path is chosen under
  split-knowledge topology constraints. The bridge is the shared observation point RQ1 probes and
  the concentration point RQ2's funnelling test probes.
- **Determinism & provenance (R1–R3).** All stochastic behaviour derives from a single
  `--sor-seed`; the seed, git SHA, and node-role→device mapping are echoed into an immutable
  `manifest.json`, and every relay event is appended to a SHA-256-sealed `events.jsonl`.
- **Containment (binding).** Every forwarder runs in an **isolated engine only**
  (`assert engine != local` or the run refuses). All traffic is self-generated to our own
  fixtures, lab-only. No external target, no live-network relay.

---

## 4. Methods (pre-registered; frozen)

This study is a **confirmatory factorial controlled comparison**; the design, variables, seeds,
detectors, and analysis were frozen and hashed on 2026-07-19 before any confirmatory cell ran.

### 4.1 Design matrix

Cells are organised per RQ with the other factors held at their declared control:

- **RQ1 (linkability):** bridge ∈ {off, on, on+padding} — 3 levels; topology held at
  single-house, selector `static`. (bridge-off+padding is declared **N/A** — padding is defined
  only for bridge-on.)
- **RQ2 (anonymity set):** topology ∈ {1-house-N, bridge-federated, directory-federated} at
  **matched total node count N** — 3 levels; bridge held off, selector `static`.

Full crossing is not run. Run order is randomised within each cell and the control arm is
interleaved before and after treatments so grid calibration drift is caught. All stochastic
elements are seed-controlled.

### 4.2 Dependent variables

- **RQ1 — correlation AUC.** Area under the ROC of the frozen flow-correlation detector scoring
  (entry-segment, exit-segment) pairs as same/different circuit, measured from the real per-hop
  pcaps. Unit of analysis: the **(entry, exit) pair**; 95% CI by **bootstrap over circuit
  pairs**.
- **RQ2 — anonymity-set entropy H.** Shannon entropy of the **adversary's posterior over
  candidate senders per circuit**; effective set size S = 2^H [Serjantov2002], normalized
  d = H/log₂N [Diaz2002]; **Miller–Madow** finite-sample bias correction; 95% CI by **bootstrap
  over circuits**. Unit of analysis: the **circuit**. **ΔH = H(federated) − H(single-house,
  matched N).**
  > *Construction (ratified).* The prereg pins this DV as a per-circuit posterior but does not
  > give the posterior **construction rule**. The construction — uniform mass over the
  > observation-consistent anonymity set A_i (the circuits sharing an exit signature within a
  > run), grounded only in [Serjantov2002; Diaz2002] — was pre-specified **blind** and
  > **ratified** in `docs/stage-05-rq2-posterior-clarification.md`. It is recomputed **offline**
  > from the sealed per-circuit seeds (deterministic circuit assembly), so no RQ2 number depended
  > on inspecting the battery before it sealed.

### 4.3 Sampling & power

**R = 30** independent seeded runs per cell; each run builds **C = 50** circuits (≥ 1500 scored
pairs per cell for RQ1). The target is **precision, not a formal power analysis**: ≥ 1500 pairs
yields an expected bootstrap 95% CI half-width on AUC ≤ 0.03, enough to resolve the RQ1 floor
away from 0.5. One base seed **S0 = 20260719**; per-cell seed = `SHA256(S0 ‖ cell_id ‖ run_index)`
truncated to u64, echoed into every manifest. **Stopping rule:** all cells × R runs run to
completion — **no optional stopping, no interim looks**; an uninformative cell is reported
**inconclusive**, never extended to chase significance.

**Apparatus (disclosed).** All relay hops ran as **isolated Docker containers on a single engine
host** (the laptop; `grid/device-map.json`, `isolated_engine_host_count = 1`, Docker 27.5.1).
Node distinctness is thus container-level
(≥ 3 distinct containers per circuit), and matched-N is pinned from the containerised node count
per manifest; cross-machine effects are out of scope (§7).

### 4.4 Frozen detectors and the instrument-validation gate

Detectors (correlator, entropy estimator, classifier) are written and **calibrated only on the
instrument-validation fixtures** — known-linked/known-unlinked control pairs and
equiprobable-sender synthetic sets — **before any confirmatory cell is run**; **no per-cell
tuning** is permitted. The battery ran only after all six boolean gate items passed green:
(1) 3-hop end-to-end delivery with per-hop pcap + checksum; (2) seeded reproducibility (same seed
→ identical circuit-build sequence); (3) correlator calibration (known-linked AUC ≈ 1,
known-unlinked ≈ 0.5); (4) entropy calibration (H = log₂N for N equiprobable senders);
(5) isolation (`assert engine != local` or refuse); (6) provenance integrity (replayed fixture →
schema-valid `events.jsonl` whose SHA-256 matches the manifest; append-only).

### 4.5 Analysis plan

Effect size + 95% CI for **every** comparison; p-values never reported alone. All inference is
bootstrap/permutation-based (10,000 resamples, **BCa** intervals; 3-seed spot-check to MC error).

- **RQ1-P1 (leak).** Bridge-on correlation AUC, bootstrap 95% CI. **Confirmation gate = CI
  excludes 0.5** (leak present); **null** if CI includes 0.5. Materiality is a *separate* label:
  CI lower bound ≥ **0.60** ⇒ "material leak"; between 0.5 and 0.60 ⇒ "weak-but-real leak."
- **RQ1-P2 (padding efficacy).** ΔAUC = AUC(bridge-on, no-pad) − AUC(bridge-on, +pad); **paired**
  bootstrap 95% CI. Padding effective iff ΔAUC CI **> 0**.
- **RQ2-P1 (federation effect, two-sided).** ΔH bootstrap 95% CI; **the sign is not presumed.**
  **grow** if CI > 0; **honest shrink (reported with equal prominence)** if CI < 0;
  **inconclusive** if it spans 0.
- **RQ2-P3 (funnelling mechanism).** Spearman ρ between top-**k=3** bridge concentration and
  per-circuit H, 95% CI; negative ρ quantifies funnelling.
- **Multiple comparisons.** Holm–Bonferroni over the frozen **family of 7** confirmatory tests
  {RQ1-P1, RQ1-P2, RQ2-P1, RQ2-P3, RQ3-P1-perf, RQ3-P1-latency, RQ3-P2}; the 4 lead-paper tests
  are reported at Holm-adjusted multipliers 7, 6, 5, 4 (conservative embedding — see
  `docs/stage-05-holm-clarification.md`, ratified). EXPLORATORY results (QUIC transport; any
  post-hoc contrast) are labelled and excluded from the confirmatory column.
- **Data exclusion (pre-data).** A run is quarantined (logged, never silently dropped) **only**
  on a data-integrity failure (SHA mismatch, pcap checksum failure, in-place edit, or
  non-reproducing seed). **No performance-based exclusions.**
- **Bootstrap implementation (method-faithful, not method-substituted).** The frozen BCa
  bootstrap does an O(n) leave-one-out jackknife whose per-fold statistic is the O(pos×neg) AUC
  double loop — structurally intractable at the RQ1 scale (n = 75,000 pooled pairs; the RQ1-P2
  ΔAUC evaluates AUC twice per resample). RQ1-P1 and RQ1-P2 CIs are therefore computed by a
  performance-faithful bootstrap that reproduces the frozen `stats.bootstrap_ci` **bit-for-bit**
  (identical `random.Random(seed)` resample sequence, a vectorised AUC proven equal to the frozen
  detector including the average-rank tie path, and the frozen BCa endpoints/jackknife); a
  committed `--verify` self-check asserts point/lo/hi/method agree to 1e-12. RQ2-P1 and RQ2-P3
  remain on the unmodified frozen paths. No point estimate, CI gate, or decision is changed.

---

## 5. Results

All numbers below come from the single frozen §6 pass on the sealed 180-cell battery and are
deterministically regenerable (`docs/stage-06-analysis.md`; seed S0 = 20260719; 10,000 BCa
resamples; α = 0.05). Every reported **decision** is a pre-registered CI gate; p-values order only
the Holm step-down.

### 5.1 Instrument-validation gate report

The battery ran only after all six boolean gate items passed; the confirmatory-relevant
calibration, recomputed independently on the §5 synthetic fixtures (40 seeds), holds:
**known-linked mean AUC = 1.0000** (criterion ≥ 0.95) and **known-unlinked mean AUC = 0.5036**
(criterion 0.40–0.60). Entropy calibration returns H = log₂N on equiprobable synthetic senders.
Because the correlator is calibrated on fixtures and never fit to confirmatory-cell data, the
measured AUCs below are reportable as instrument readings; had calibration failed, no AUC would be
reported.

### 5.2 RQ1 — bridge linkability

**RQ1-P1 (leak).** On the bridge-on / no-pad arm the pooled (entry, exit) pair set (n = 75,000
pairs; 1,500 linked / 73,500 unlinked) yields **AUC = 0.4660, BCa 95% CI [0.4523, 0.4798]**. The
CI excludes 0.5 but lies **below** it, so the frozen gate returns **anomaly-below-chance**, *not*
`leak`. The correlator does not link entry↔exit segments better than chance on the bridge-on
traffic; it sits marginally below chance — an unexplained artifact of the pooled correlator on this
as-instrumented traffic (this is the **no-pad** arm, so no cover stream is involved), not a
linkability finding — so we report **no measurable leak**. The two-sided rejection at AUC = 0.5 is
in the wrong direction and is not evidence of linkability.

**RQ1-P2 (padding efficacy).** Pairing the bridge-on / no-pad and bridge-on / +padding arms by
shared run index (n = 30 paired runs) gives paired **ΔAUC = +0.0113, BCa 95% CI [−0.0025,
+0.0234]** (per-run ΔAUCᵢ range ≈ [−0.080, +0.081], straddling zero). The CI spans 0 → frozen gate
**padding-ineffective** (raw p = 0.091). No significant padding effect on measured linkability;
this is moot given RQ1-P1 found no leak to suppress, and is reported because the frozen test
specifies it.

### 5.3 RQ2 — anonymity-set effect of federation

**RQ2-P1 (federation effect, two-sided).** Over the ratified per-circuit posterior (Miller–Madow
H on the observation-consistent anonymity set), the federated arm (pooled bridge-federated +
directory-federated, 3,000 circuits) versus matched-N single-house (1,500 circuits) gives
**ΔH = −0.9587 bits, BCa 95% CI [−1.0559, −0.8641]**. The CI is strictly below 0 → frozen gate
**shrink**. Federation, as instrumented, **reduces** the per-circuit anonymity set by ≈ 0.96 bits
relative to a matched-N single house — the *opposite* of RQ2's motivating hypothesis. Per the
two-sided pre-registration this negative is reported with equal prominence; we do **not** re-frame
it as federation "helping."

**RQ2-P3 (funnelling mechanism).** Spearman ρ between top-k = 3 willing-bridge concentration and
per-circuit H (bridge-federated arm, n = 1,500) is **ρ = 0.0000, CI [0.0000, 0.0000]**
(percentile fallback) → **inconclusive**. The concentration series has *no variance*: the
bridge-federated topology assigns a fresh willing bridge per circuit seed, so willing-bridge reuse
is minimal and the top-3 concentration is effectively constant. Spearman is undefined on a
zero-variance covariate. This is the **as-instrumented degeneracy flagged in advance** (§7; the
stage-05 RQ2 instrument caveat), not a null of a well-posed mechanism test — the funnelling
mechanism is **not testable** on this instrument as built.

### 5.4 Holm-corrected confirmatory summary

Holm–Bonferroni over the frozen family of 7 (reporting the 4 lead-paper tests at conservative
multipliers 7, 6, 5, 4, ordered by ascending raw p):

| Test | Effect | Point | 95% CI (BCa) | Frozen decision | raw p | Holm adj-p (m=7) | Reject @ .05 |
|---|---|---|---|---|---|---|---|
| RQ1-P1 | AUC (bridge-on) | 0.4660 | [0.4523, 0.4798] | anomaly-below-chance | 0.000 | 0.000 | yes* |
| RQ2-P1 | ΔH (fed − single) | −0.9587 bits | [−1.0559, −0.8641] | shrink | 0.000 | 0.000 | yes |
| RQ1-P2 | ΔAUC (nopad − pad) | +0.0113 | [−0.0025, +0.0234] | padding-ineffective | 0.091 | 0.456 | no |
| RQ2-P3 | Spearman ρ | 0.0000 | [0.0000, 0.0000] | inconclusive | 1.000 | 1.000 | no |

`*` RQ1-P1 rejects `H0: AUC = 0.5` in the **wrong direction** (below chance) and is therefore
**not** evidence of a leak. Two tests survive Holm at α = 0.05: RQ1-P1 (anomaly-below-chance) and
RQ2-P1 (shrink — a negative effect). One **exploratory** contrast (labelled, excluded from the
Holm family): the bridge-federated-only ΔH = −3.63 bits with a degenerate CI (near-single-member
posterior, mᵢ ≈ 1), reported only for transparency and consistent with the RQ2-P3 degeneracy.

---

## 6. Discussion

**A double null/negative, reported without spin.** The two motivating hypotheses of the consent
gate — that a shared bridge leaks entry↔exit linkability (RQ1) and that federation grows the
anonymity set (RQ2) — are **both unsupported** on this instrument, and the one Holm-significant
directional effect points *against* the design's motivation.

**RQ1 — no bridge leak to close.** The frozen, fixture-calibrated correlator (linked AUC 1.00,
unlinked 0.50) reads the bridge-on traffic at AUC 0.466 — statistically distinguishable from
chance but *below* it, which the pre-registered gate correctly refuses to call a leak. We do not
have a substantiated mechanism for the slight below-chance offset; it is a small artifact of the
pooled correlator on this as-instrumented traffic (and it is *not* a padding effect — this is the
no-pad arm, which carries no cover stream). Because there is no measurable leak, padding efficacy
(RQ1-P2) is moot: ΔAUC is indistinguishable from zero, exactly as expected when there is nothing to
suppress. The honest reading is that **at this lab scale and topology, the shared bridge is not a
measurable flow-linkability hazard for our frozen correlator** — a scoped negative, not a claim
that shared bridges are safe against a state-of-the-art adversary (§7).

**RQ2 — federation shrinks the anonymity set.** The evidentiary core is the Holm-significant
ΔH = −0.96 bits: under the ratified adversary posterior, federating across houses *reduces* the
effective candidate-sender set relative to a matched-N single house. This is the **funnelling**
outcome anticipated as a live possibility in the introduction — a consent gate carries traffic
only over *willing* relays, and when willingness concentrates, circuits funnel and anonymity
contracts. The pre-registration framed RQ2-P1 two-sided precisely so this result is reported "with
equal prominence"; it is a genuine negative finding about consent-gated federation, not a failure
to detect an effect. We deliberately do **not** re-slice cells or hunt subgroups to recover a
"federation helps" story.

**Why the funnelling mechanism test is inconclusive.** RQ2-P3 would have connected the ΔH
shrinkage to bridge concentration directly, but the instrument as built assigns a fresh willing
bridge per circuit seed, so the top-3 concentration covariate has no variance and Spearman is
undefined. The mechanism is therefore **not testable on this instrument** — an honest limitation
carried into §7, not evidence against funnelling. The exploratory bridge-federated-only
ΔH = −3.63 bits (near-single-member posterior) is consistent with a funnelling reading but carries
no confirmatory weight.

**Takeaway.** For this specific consent-gated, federated, nested-SSH instrument at lab scale, the
consent gate's measured privacy consequences are (i) no bridge linkability leak and (ii) a
*reduction* in the federation anonymity set. Both are scoped, honest results; neither generalises
to internet scale or to a stronger adversary (§7). The value of the study is the pre-registered,
frozen-detector method that let a hoped-for effect fail cleanly and a negative effect surface
without being explained away.

---

## 7. Limitations & threats to validity

- **Scale / adversary model (External).** The grid is a single laptop (isolated-docker), few houses; this
  is **not** internet-scale and **not** a global passive adversary. Claims are scoped to the
  tested topology/scale; entropy CIs are wide at small node counts (accepted, node counts
  reported).
- **Node distribution (External, disclosed).** All relay hops executed as **isolated Docker
  containers on a single engine host** (the laptop; `isolated_engine_host_count = 1`, recorded in
  `grid/device-map.json`). The two phones were **pinned consenting-node labels, not forwarders** — they
  cannot host an isolated engine, were verified reachable only by a single grid-pin probe, and
  carried no measured traffic (`PHONE-ROLE-AUDIT.md`). Node *distinctness* for RQ1/RQ2 is therefore container-level
  (≥ 3 distinct containers per circuit), not physical-machine-level; matched-N is pinned from the
  containerised node count per manifest. This satisfies the containment law (every forwarder runs
  in an isolated engine, `engine ≠ local`) but means cross-machine timing effects are **out of
  scope**; physical multi-host distribution is named future work.
- **Construct.** Self-generated fixture traffic is not real user traffic (inherent to lab
  measurement; fixtures versioned/checksummed). A single correlator's AUC stands in for
  "linkability" and plug-in H for "anonymity" — mitigated by fixture calibration (§4.4) and by
  reporting S = 2^H and normalized d; a second entropy estimator (NSB) is reported EXPLORATORY as
  a sensitivity check.
- **Internal.** Thermal/background load and device heterogeneity are mitigated by randomised
  order, interleaved controls, per-session idle baselines, and a pinned node-role→device mapping.
  Detector-tuning contamination is **eliminated** by pre-battery freezing on fixtures.
- **RQ2 construction dependency.** The RQ2 result depends on the ratified posterior construction
  (§4.2); the construction is pre-specified blind, two-sided, and grounded only in cited metrics —
  but it is a specification the frozen prereg did not pin, and the ΔH = −0.96 bits finding should
  be read as conditional on it.
- **Funnelling mechanism not testable as-instrumented (RQ2-P3).** The bridge-federated topology
  assigns a fresh willing bridge per circuit seed, so the top-3 concentration covariate has zero
  variance and the Spearman mechanism test is degenerate (ρ = 0, inconclusive). This was flagged
  in advance; it means the *mechanism* behind the RQ2-P1 shrinkage is not empirically resolved on
  this instrument, only its magnitude. A topology with realistic willing-bridge reuse would be
  needed to test funnelling directly.
- **Dual-use (ethics).** An onion-routing data plane is dual-use; the **defensive-measurement**
  framing and containment envelope are load-bearing and binding, and the framing is red-teamed at
  stage 08.

---

## 8. Deviations from pre-registration

Tracked only in stage-05 `sor-consent-deviations.md` (none edit the frozen prereg). Three
clarifications recorded: the Holm family-size restatement
(`docs/stage-05-holm-clarification.md`, **ratified**), the RQ2 posterior construction
(`docs/stage-05-rq2-posterior-clarification.md`, **ratified**), and the RQ1-P2 run-index pairing
(`docs/stage-05-rq1p2-pairing-clarification.md`, **freeze-derived / ratified**). One
implementation note carried in §4.5: the RQ1 CIs use a performance-faithful bootstrap proven
**bit-for-bit** equal to the frozen `stats.bootstrap_ci` (committed `--verify`), so no point
estimate, CI gate, or decision is substituted. The frozen prereg SHA is unchanged
(`f22331a72e…`).

---

## References

- **[Chaum1981]** Chaum, D. L. (1981). Untraceable Electronic Mail, Return Addresses, and Digital
  Pseudonyms. *CACM* 24(2), 84–90. https://doi.org/10.1145/358549.358563
- **[Reed1997]** Reed, M. G., Syverson, P. F., & Goldschlag, D. M. (1997). Anonymous Connections
  and Onion Routing. *IEEE S&P 1997*, 44–54. https://doi.org/10.1109/secpri.1997.601314
- **[Dingledine2004]** Dingledine, R., Mathewson, N., & Syverson, P. (2004). Tor: The
  Second-Generation Onion Router. *USENIX Security 2004*.
- **[Egners2012]** Egners, A., Gatzen, D., Panchenko, A., & Meyer, U. (2012). Introducing SOR:
  SSH-based Onion Routing. *IEEE WAINA 2012*, 280–286. https://doi.org/10.1109/WAINA.2012.89
- **[Honda2005]** Honda, O., et al. (2005). Understanding TCP over TCP. *SPIE 6011*.
  https://doi.org/10.1117/12.630496
- **[Michel2023]** Michel, F., & Bonaventure, O. (2023). Towards SSH3. arXiv:2312.08396.
- **[AlAzad2023]** Al Azad, M. W., et al. (2023). DarkHorse. *IEEE LCN 2023*. arXiv:2307.02429.
- **[MurdochD05]** Murdoch, S. J., & Danezis, G. (2005). Low-Cost Traffic Analysis of Tor.
  *IEEE S&P 2005*, 183–195. https://doi.org/10.1109/SP.2005.12
- **[JohnsonWJSS13]** Johnson, A., et al. (2013). Users Get Routed. *ACM CCS 2013*, 337–348.
  https://doi.org/10.1145/2508859.2516651
- **[NasrBH18]** Nasr, M., Bahramali, A., & Houmansadr, A. (2018). DeepCorr. *ACM CCS 2018*,
  1962–1976. https://doi.org/10.1145/3243734.3243824
- **[OhYMH22]** Oh, S. E., et al. (2022). DeepCoFFEA. *IEEE S&P 2022*, 1915–1932.
  https://doi.org/10.1109/SP46214.2022.9833801
- **[RahmanSMGW20]** Rahman, M. S., et al. (2020). Tik-Tok. *PoPETs* 2020(3).
  https://doi.org/10.2478/popets-2020-0043
- **[SirinamIJW18]** Sirinam, P., et al. (2018). Deep Fingerprinting. *ACM CCS 2018*, 1928–1943.
  https://doi.org/10.1145/3243734.3243768
- **[Serjantov2002]** Serjantov, A., & Danezis, G. (2002). Towards an Information Theoretic Metric
  for Anonymity. *PET 2002*, LNCS 2482, 41–53. https://doi.org/10.1007/3-540-36467-6_4
- **[Diaz2002]** Díaz, C., et al. (2002). Towards Measuring Anonymity. *PET 2002*, LNCS 2482,
  54–68. https://doi.org/10.1007/3-540-36467-6_5
- **[Douceur2002]** Douceur, J. R. (2002). The Sybil Attack. *IPTPS 2002*, LNCS 2429, 251–260.
  https://doi.org/10.1007/3-540-45748-8_24
- **[Danezis2003]** Danezis, G. (2003). Statistical Disclosure Attacks. *IFIP SEC 2003*.
- **[Winter2016]** Winter, P., et al. (2016). Identifying and Characterizing Sybils in the Tor
  Network. *USENIX Security 2016*, 1169–1185.
- **[Clarke2000]** Clarke, I., et al. (2000/2001). Freenet. *Designing PETs*, LNCS 2009.
  https://doi.org/10.1007/3-540-44702-4_4
- **[Vasserman2009]** Vasserman, E. Y., et al. (2009). Membership-Concealing Overlay Networks.
  *ACM CCS 2009*, 390–399. https://doi.org/10.1145/1653662.1653709
- **[Danezis2010]** Danezis, G., et al. (2010). Drac. *PETS 2010*, LNCS 6205, 202–219.
  https://doi.org/10.1007/978-3-642-14527-8_12
- **[Mittal2012]** Mittal, P., Wright, M., & Borisov, N. (2012). Pisces. *NDSS 2013*.
  arXiv:1208.6326.
- **[Mittal2012b]** Mittal, P., Caesar, M., & Borisov, N. (2012). X-Vine. *NDSS 2012*.
  arXiv:1109.0971.
- **[Zhou2011]** Zhou, P., et al. (2011/2013). STor. arXiv:1110.5794.

*(Full bibliography: `~/coding/sci-method/stages/01-literature/output/sor-consent-bibliography.md`.
Integrity flags carried forward: [Stutzbach2006] secondary-sourced; [Constantinides2026] recent
preprint — neither is load-bearing in this lead paper.)*
