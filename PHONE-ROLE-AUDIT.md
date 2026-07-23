# Phone-role audit

*Added 2026-07-22 after a post-hoc audit of what the two phones (`fp6`, `tril`)
actually did during the sealed confirmatory battery. This note exists so the record
is self-disclosing. It changes **no measured number** — see "Does this affect the
findings?" below.*

## What was claimed vs. what happened

Earlier wording described the two phones as "consenting **endpoints**" in a way that
could be read as *active, continuous participants* that started/ended conversations
throughout the study. The audit shows that is an **overstatement**. This note gives
the precise, evidenced role.

## What the phones actually did

- **They were pinned in the grid inventory** as logical consenting-node *labels*:
  `fp6` = house-B, `tril` = house-C (`code/python/.../grid.py`, `GRID_INVENTORY`).
- **They cannot host an isolated engine** — both report `can_host_engine = false`
  (`tril` is Termux with no Docker). Per the containment law, a device that cannot
  host an isolated engine **can never run a forwarder**.
- **They were probed once** for SSH reachability at grid-pin time — a single
  best-effort `ssh <alias> true` check (`grid.py::_probe_ssh`), **not** continuous
  monitoring, and with **no Tailscale-specific health check**.

## What the phones did NOT do

- **They forwarded nothing.** Every SOR hop ran as a Docker container on the laptop.
- **No measured traffic traversed them.** All 27,000 per-hop pcaps and every `nodes`
  entry in the confirmatory manifests are `"engine": "docker"` containers. A
  word-boundary search for `fp6`/`tril` across the confirmatory manifests returns
  **zero** hits.
- **They were not continuously verified online.** The confirmatory grid-pin
  (`2026-07-20T06:01:52Z`) recorded both phones reachable — but that is a single
  snapshot **~10 min before** the battery began (`06:11:41Z`). The battery ran ~23 h
  (`→ 2026-07-21T05:24:09Z`) with **no probe during or at the end**. `tril` was in
  fact recorded **down** (`devices_down=['tril']`) at 02:46, 02:52, 02:53 and 04:39Z
  earlier that same night.

## Does this affect the findings? No.

Every measured quantity (RQ1 linkability AUC, RQ2 ΔH, RQ2-P3 mix ρ, RQ3 churn) is
computed from the laptop's Docker-container circuits. The phones were **never in the
data path** — by design (`can_host_engine = false`). Therefore a phone being up or
down at any instant **cannot** have altered a single data point. The core scope was
always disclosed honestly as `isolated_engine_host_count = 1`.

The correction here is one of **framing/precision**, not data integrity: the phones
were a one-time reachability probe plus logical topology labels, not active
forwarding participants.

## Why we did NOT re-run

Re-running a **frozen, SHA-256-sealed confirmatory battery** and choosing which run to
report would be a garden-of-forking-paths / p-hacking violation — it would destroy the
pre-registration guarantee that is the whole point of the study. A halt-on-outage
failsafe would also protect nothing here, because no measured data ever depended on
phone connectivity.

A genuinely device-distributed version (phones as real forwarders,
`isolated_engine_host_count > 1`), and a container-simulated multi-pool version, are
named **future work** and are the correct place for connectivity failsafes. See
`prereg/NEXT-EXPERIMENT-DRAFT.md`.
