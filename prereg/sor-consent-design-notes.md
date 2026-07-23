# Design notes — sor-consent (rationale + alternatives)

Companion to `sor-consent-prereg.md` (DRAFT). Records *why* each design choice was made and
what was rejected, so the stage-08 reviewer and the human approver can audit the reasoning
without reverse-engineering it from the frozen document.

## Why a shared factorial instrument (not three studies)

The three RQs interrogate one artifact — a consent-gated, federated, nested-SSH relay. Building
that data plane is the dominant cost (roadmap R1–R7, "L"). Splitting into three single-factor
studies would triplicate the instrument, lose topology×selector interactions, and underpower
each. A factorial matrix with **declared N/A cells** amortizes the build and keeps every DV
traceable to the same event log. The cost — full crossing is expensive — is avoided by running
each RQ against the *other* factors held at their control, not the full Cartesian product.

## Why the thresholds are set where they are (all [APPROVAL])

These are the numbers the GOAL left symbolic; they are the substance of the human freeze gate.

- **0.60 AUC (RQ1 materiality label / RQ3 ceiling):** 0.50 is chance; 0.60 is the smallest
  discrimination we call a *material* leak / a *usable* fingerprint. Note the asymmetry introduced
  by D2: for **RQ1**, 0.60 is only a **materiality label** (the confirmation gate is CI-excludes-0.5);
  for **RQ3**, 0.60 **is** the gate (P2 requires the rebuild-classifier CI upper bound ≤ 0.60),
  because RQ3's claim is explicitly "not a *usable* fingerprint" — a practical-materiality bar, not
  bare significance. Both use the same 0.60 yardstick for what "material discrimination" means.
- **X = 10 pp throughput margin, Y = 100 ms added latency (RQ3):** the grid is a LAN of two
  phones + a laptop; base hop latencies are small, so 100 ms is a generous but finite added-
  latency budget over the best baseline. 10 pp is a modest, real retention advantage — small
  enough to be attainable, large enough to matter. Both are reconfirmed against the §5 baseline
  latency measurements *before* freeze, so we are not guessing.
- **Matched-N rule (RQ2):** single-house arm = total consenting nodes of the federated arm. This
  is the fair comparison — it isolates *topology* from mere *node count*. The honest-null
  hypothesis (federation shrinks the set by funneling) is only interpretable against a
  same-size single house.
- **R = 30 runs × C = 50 circuits:** justified as a **precision target**, stated honestly, not a
  false-precision power calculation. AUC CI half-width ≤ ~0.03 at ≥1500 pairs/cell resolves the
  0.60 floor cleanly. 30 runs satisfies the stochastic-system repetition rule. Final R/C are
  confirmed against the calibration CI widths seen at the §5 gate.

## Why bootstrap/permutation inference (not parametric)

AUC, entropy, and throughput ratios have no clean parametric sampling distribution at these N;
BCa bootstrap and permutation tests are assumption-light and match the torah-els house style.
This sidesteps normality/variance-homogeneity failures entirely (`rigor-standards §Statistics`).

## Why Holm across all three RQ families

The GOAL asks for multiplicity correction across the three families. Holm–Bonferroni over the
7 confirmatory tests is the rigor-standards default, controls FWER, and is more powerful than
plain Bonferroni. FDR was rejected: 7 tests is a small, pre-declared confirmatory family, not a
large exploratory screen. The transport arm and any post-hoc contrast are EXPLORATORY and
excluded from the corrected family.

## Alternatives considered and rejected

- **Live-network / internet-scale measurement** — rejected: outside the containment envelope
  (hard stop, GOAL (b)) and the scientific scope. The paper claims a *local, consent-gated*
  model, not a Tor-scale bound.
- **Analytical-only anonymity bound** — rejected for RQ2: the funnel effect is emergent from real
  consent behaviour + churn; a graph model would beg the question the experiment exists to answer.
- **Bit-identical detector reuse without recalibration** — rejected: the §5 calibration gates
  (P3-RQ1, P2-RQ2) are the construct-validity backbone; a detector that cannot score a
  known-linked pair at AUC≈1 or return log2(N) on equiprobable senders is not trusted.
- **Optional stopping / sequential peeking** — rejected outright (`rigor-standards §Statistics`);
  fixed R, inconclusive-is-a-result.
- **Dropping the agent arm silently if unfunded** — rejected: it is pre-declared as a reduced-arm
  contingency (§2), so a {static, random} battery is an honest planned outcome, not a post-hoc cut.

## Honest-expectation guardrails (from GOAL)

RQ1 likely confirms a leak; RQ3's agent arm likely helps *somewhat*; **RQ2 is a genuine
coin-flip** and a shrink result is fully publishable. The matched-N rule, the two-sided ΔH test,
and the equal-prominence reporting mandate are all in place specifically so the design cannot be
read as tuned to make "federation helps." The stage-08 review is charged with red-teaming exactly
this (confirmatory/exploratory labeling, RQ2 null framing, multiplicity, containment claims).

## Decisions taken (2026-07-19, pre-freeze — mirror of prereg §9)

1. **Agent selector arm (D1):** run on a **pinned local/open-weight model** from the hackhouse
   agent fabric — confirmatory, $0, no paid-budget gate. Rationale: static-vs-random alone is a
   low-caliber contrast (random already re-rolls under churn), and the GOAL's budget gate only ever
   bound a *paid frontier* model — nothing requires the "agent" to be paid. A local model answers
   RQ3's real question, drops the budget dependency, and pins reproducibly. Rejected: fund a
   frontier model (unnecessary cost + hosted-endpoint drift) and drop-to-{static,random} (thin RQ3).
   Data-driven fallback: funded follow-on only if the local model fails §5 calibration.
2. **RQ1 confirmation gate (D2):** confirmation = **CI excludes 0.5**; the 0.60 becomes a
   *materiality label* (weak-but-real vs material), not the gate. Rationale: the original
   "AUC > floor AND CI excludes 0.5" left a dead zone (e.g. AUC 0.57 / CI [0.53,0.61]) that was
   neither confirmable nor refutable — a reviewer would read the floor as hiding a real leak. The
   new gate mirrors the stage-02 falsification condition and reports raw AUC+CI regardless.
3. **Transport arm (D3):** **TCP-nested confirmatory, QUIC-nested `ssh3` EXPLORATORY.** Rationale:
   orthogonal to all three RQs, a weak lit-gap, and promoting it would double every cell + the
   build + the multiplicity family for a secondary question.
4. **Containment (D4):** **unchanged, verbatim** — the dual-use ethical backbone; no reason to touch.
5. **Freeze (D5):** **deferred** — the document stays DRAFT until the operator says "freeze," to
   keep the packaging fork (below) open. On sign-off: flip DRAFT→FROZEN, compute SHA-256 →
   `sor-consent-prereg.sha256`, record in the run manifest.

## Packaging fork — one paper vs several (D6, explicit circle-back record)

**The fork:** bundle all three RQs into one paper, or split per-RQ.

**Why the evidence cleaves 2-and-1, not 1-1-1:** RQ1 (bridge linkability) and RQ2 (federation's
anonymity-set effect) are two halves of one anonymity story — same metrics (AUC, entropy), same
reader (a privacy-measurement venue). RQ1 alone ("a bridge leaks") is thin, and splitting RQ1 from
RQ2 would be salami-slicing. RQ3 (churn resilience + agent-managed rebuilds) is a different axis
(availability / AI-network-control) with a different reviewer pool. So the natural fracture is
**RQ1+RQ2 | RQ3**; three papers is over-fragmented.

**Decision (revisable at stage 07):** lead paper = **G4 + RQ1 + RQ2**; **RQ3 = designated severable
follow-on.** This matches roadmap Phase P and is now firmer because D1 makes RQ3 a $0 confirmatory
arm, not a budget-fragile one.

**Why deferring is free and not salami-slicing:** the three concerns — *instrument* (what we build),
*prereg* (what we commit to test), *paper(s)* (how we package) — are separable. We **build once**
(R1–R7), **pre-register all three RQs as confirmatory now**, **run the battery once**, and decide
packaging at **stage 07** from the observed results. They remain one pre-registered instrument +
battery; the shared prereg + Holm family are disclosed in every resulting paper (more rigorous, not
less). Pre-registering all three only buys the option to publish RQ3 as confirmatory later; dropping
it from the prereg would forfeit that.

**Circle-back triggers (revisit at stage 07):** RQ3 strong enough to headline → firm split; RQ3 thin
→ fold in as a section of the lead paper; a target venue's scope forces a cut. Changes to a frozen
item go in the stage-05 deviations log; pure drafting/packaging changes are stage-07 notes.

## Build-implementation detail — RQ3 agent backend (2026-07-19, build agent)

> Recorded by the build agent under explicit operator authorization. This is the
> concrete *implementation* of design decision **D1** above (which already commits
> the `agent` arm to a pinned local/open-weight model, confirmatory, $0). It adds
> no IV and changes no frozen item — it documents *how* D1 was built. Any move to a
> `{OSS-local vs Claude/frontier}` **capability-tier comparison** would be a
> design-matrix change (a new IV factor) and must go through the stage-05
> deviations log, never a silent edit.

- **Confirmatory `agent` backend = local Ollama model** (default `qwen2.5:3b`),
  chosen for reproducibility over raw capability — the rebuild decision is a
  low-complexity ranking (order the live pool by churn stability, take `hops`),
  a regime where a small local model matches a frontier one. Reproducibility is
  engineered in:
  - inference pinned: `temperature=0` + per-run `seed`;
  - every decision **cached keyed by `(seed, state-hash)`** → byte-identical
    replay regardless of residual model nondeterminism;
  - any model/parse/validation failure → deterministic local heuristic fallback
    (fewest-kills-first), so a run never breaks or silently drifts;
  - model **id + weights digest** pinned into `manifest.json` (`selector_backend`);
    per-state decision log written to the run's `selector.json` sidecar.
  - Code: `cmd_chat/sor/agent_selector.py::OllamaAgentPolicy`; pluggable seam
    `cmd_chat/sor/selector.py::SelectorPolicy`.

- **Claude Code / paid frontier arm = EXPLORATORY hook only, not wired**
  (`ClaudeExploratoryPolicy`): makes no paid call, refuses to serve as a
  confirmatory backend (GOAL autonomy envelope (c), human + budget gated).

- **Containment:** the selector's model query is a **local** call to
  `localhost:11434` — a measurement-side decision, not relay/data-plane traffic,
  reaching no external target. §Containment is unaffected.
