# Glossary — plain-English definitions

Every technical term used in this project, explained for someone who is **not** a
scientist or a security specialist. If a term in the papers confuses you, look here
first.

## The thing we built

- **Onion relay / onion routing.** A way of sending a message through several
  computers ("hops") in a chain, wrapped in layers of encryption like the layers of
  an onion. Each hop peels one layer and only learns the *next* hop — no single hop
  knows both who sent the message and who will finally receive it. Tor is the famous
  example.
- **Nested SSH.** We built those encryption layers using ordinary SSH (the secure
  login tool admins use every day), one SSH tunnel inside another. "Nested" = tunnels
  inside tunnels.
- **Hop / relay / forwarder.** One computer in the chain that passes traffic along.
- **Circuit.** One complete chain of hops that a message travels through (in our
  study, always **3 hops**: entry → middle → exit).
- **Bridge.** A **shared** hop that many circuits pass through. Sharing could be good
  (more people blend together) or bad (one node sees a lot) — measuring that is RQ1.
- **Consent-gated.** Before a hop agrees to carry a circuit, it performs a signed
  "do you accept this?" handshake. A relay can *refuse*. This is the novel ingredient
  we set out to measure.
- **House.** One independent **Hack House instance** — a self-contained chat-relay
  server (one community's private deployment) with its own pool of relay nodes and its
  own cryptographic identities. A "house" is **not** a building or a location; it is a
  software deployment. *(In this study the houses were logical groupings on our lab grid:
  house-A = the laptop's pool of relay containers; house-B and house-C = the two phones
  acting as consenting nodes. All forwarding hops were containers on the one laptop.)*
- **Federated / federation.** Linking two or more separate **houses** (see above) so
  their relay pools **combine into one larger shared crowd**, with each circuit built to
  **span ≥ 2 houses** so no single house's logs ever contain a whole path
  ("split-knowledge"). Two mechanisms: a shared **bridge** node that blind-forwards
  encrypted bytes between houses (it holds no chat key for either), or a **directory** in
  which houses exchange signed rosters of their nodes. RQ2 asks whether federating this
  way actually enlarges your hiding crowd.
- **Endpoint vs forwarder.** An **endpoint** is a phone/computer that *starts or ends*
  a conversation. A **forwarder** is a hop in the middle. In our study the two phones
  **never forwarded** anyone's traffic (they cannot host an isolated engine). They were
  pinned as logical consenting-node *labels* and probed reachable once at grid-pin time;
  no measured traffic passed through them. See `PHONE-ROLE-AUDIT.md`.
- **Measurement instrument (not a service).** We did **not** build a product for people
  to hide their traffic. We built a lab rig whose only purpose is to be *measured* — like
  a crash-test car, not a car you drive to work.

## How we measured it

- **Linkability.** Can an eavesdropper tell that "person A talking here" and "traffic
  leaving there" are the *same* conversation? Low linkability = good privacy.
- **Flow correlation.** The specific attack that tries to match an incoming traffic
  pattern to an outgoing one by their timing/size, to break linkability.
- **AUC (Area Under the Curve).** A score from 0 to 1 for how well a detector tells
  "linked" from "not linked." **0.5 = a coin flip** (useless / no information).
  1.0 = perfect. Our bridge scored **0.466** — *below* a coin flip — meaning the
  attacker learned **nothing** usable. (Above 0.5 would mean a leak.)
- **Anonymity set.** The crowd you blend into. If 8 people could equally have sent a
  message, your anonymity set is 8. Bigger = better hiding.
- **Entropy / bits (H).** The mathematical size of that crowd. Measured in **bits**:
  `H = log2(crowd size)`. So 3 bits = a crowd of 8 (2³), 4 bits = 16, etc. **Losing
  0.96 bits** means the effective crowd roughly *halved*.
- **Mix vs funnel.** Two ways to read "many circuits sharing few bridges." A **funnel**
  would *shrink* the crowd (bad). A **mix** *grows* it by making circuits look alike
  (good, like shuffling cards together). RQ2's follow-up found our design behaves like
  a **mix**.
- **Padding / cover traffic.** Extra dummy data added to hide the real traffic pattern.
  Only helps if there's a leak to hide — RQ1 found no leak, so padding had nothing to do.
- **Churn.** Relays randomly dying and being replaced, the way a real volunteer network
  is unstable. RQ3 tests whether a smart path-picker copes better under churn.
- **Selector / path selection.** The logic that chooses which hops to use for each
  circuit. We compared three: **static** (always the same), **random**, and an
  **AI agent**.
- **Agent (qwen2.5:3b via Ollama).** A small, **free**, locally-run AI model (no cloud,
  `$0`) that we let pick paths, to see if "AI" beats simple rules. It **did not**.
- **Rebuild fingerprint / side-channel.** When a hop dies, the selector rebuilds the
  circuit. The *timing pattern* of those rebuilds could accidentally identify which
  selector you're using — a privacy leak of a different kind. We tested whether the AI's
  pattern was recognizable (it was borderline — we could not certify it safe).
- **Throughput / latency.** Throughput = how much data gets through; latency = how long
  it takes. An AI selector would only be worth it if it kept throughput up *and* added
  little delay *and* left no fingerprint. It cleared none of those bars convincingly.
- **pcap (packet capture).** A recorded log of the actual network packets at a hop — the
  raw evidence. We captured one per hop, per circuit (27,000 total).

## How we kept ourselves honest

- **Pre-registration ("frozen + hashed").** *Before* collecting any real data, we wrote
  down the exact plan — every test, detector, and seed — and computed a **SHA-256** of
  it (a unique digital fingerprint). That fingerprint is published. It proves we could
  **not** have quietly changed the plan after seeing results to make them look better.
- **Confirmatory vs exploratory.** **Confirmatory** = a test we committed to in advance
  and must report no matter the outcome. **Exploratory** = extra looking-around, clearly
  labelled and never dressed up as a confirmed finding.
- **Null result / negative result.** A finding that says "no effect" or "the opposite of
  what we hoped." These are **real results**, not failures. Reporting them plainly (even
  when the design's motivating idea didn't pan out) is the whole point of the paper.
- **Confidence interval (CI) + bootstrap / BCa.** Instead of a single number, we report a
  **range** we're 95% confident the true value lies in. "Bootstrap" and "BCa" are the
  standard resampling recipe used to compute that range fairly.
- **p-value.** The probability of seeing a result this extreme purely by chance. Small =
  unlikely to be a fluke. We never report a p-value alone — always with the effect size
  and CI.
- **Holm–Bonferroni correction.** When you run **many** tests, some will look
  "significant" by luck. This is a standard, conservative adjustment that raises the bar
  so flukes don't sneak through. We applied it across our **family of 7** tests.
- **Seed / reproducible.** A single starting number (`S0 = 20260719`) drives every random
  choice, so anyone re-running with the same seed gets the *identical* sequence of
  circuits. Nothing is hand-picked.
- **Sealed artifact / manifest / SHA-256.** Every one of the 36,361 output files has its
  own SHA-256 fingerprint recorded in a manifest, so any copy can be checked for
  tampering, bit for bit.

## Containment (safety)

- **Isolated engine / container / `engine != local`.** Every hop ran inside a sealed
  sandbox (a Docker container), never directly on the real computer. The code literally
  **refuses to run** a hop outside a sandbox. This guarantees the experiment couldn't
  touch the open internet or anyone's real traffic.
- **Self-generated fixture traffic.** The only data flowing through was test data we
  made up ourselves — no real users, no third parties, ever.

## Cryptography terms

- **X25519.** A modern method for two parties to agree on a shared secret. We use it so a
  hop's credential can be unlocked **only** by that specific hop — "per-recipient" sealing.
- **Ed25519.** A modern digital-signature method. Each participant signs its consent
  messages; a forged or unsigned request is rejected.
