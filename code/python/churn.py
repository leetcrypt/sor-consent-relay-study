"""R7 — Seeded churn schedule (deterministic node kill/spawn stream).

The churn generator produces a **schedule** — a reproducible list of kill/spawn
events drawn from the R1 ``Domain.CHURN`` stream — that models nodes dropping out
of and rejoining the grid over time. It is pure data: this module spins and kills
no real VM (that live half runs against the isolated hackhouse VM fabric and is
gated by the same containment law as the R4 forwarder). Producing the schedule
here, deterministically from the seed, is what lets the R7 acceptance check assert
that a fixed churn seed drives the selector to rebuild *every* dropped circuit —
verifiable entirely offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from cmd_chat.sor.config import Domain, SorRng


@dataclass(frozen=True)
class ChurnEvent:
    """One scheduled grid event at logical step ``t``. ``kind`` is ``"kill"`` or
    ``"spawn"``; ``node`` is the affected node id."""

    t: int
    kind: str  # "kill" | "spawn"
    node: str


def churn_schedule(
    seed: int,
    nodes: List[str],
    steps: int,
    kill_prob_pct: int = 30,
) -> List[ChurnEvent]:
    """Deterministically build a churn schedule over ``nodes`` for ``steps`` logical
    steps, drawing from the seed's CHURN stream alone (so the same seed yields the
    same schedule — the R7 determinism the selector check relies on).

    At each step every currently-live node may be killed with probability
    ``kill_prob_pct``%, and every currently-dead node is respawned with the same
    probability. Events are emitted in a stable (step, node) order."""
    if not nodes or steps <= 0:
        return []
    s = SorRng(seed).stream(Domain.CHURN)
    live = {n: True for n in nodes}
    events: List[ChurnEvent] = []
    for t in range(steps):
        for n in nodes:  # stable order -> stable schedule
            roll = s.next_below(100)
            if live[n]:
                if roll < kill_prob_pct:
                    live[n] = False
                    events.append(ChurnEvent(t, "kill", n))
            else:
                if roll < kill_prob_pct:
                    live[n] = True
                    events.append(ChurnEvent(t, "spawn", n))
    return events


def live_nodes_at(nodes: List[str], schedule: List[ChurnEvent], t: int) -> List[str]:
    """The set of live nodes at (through the end of) step ``t``, replaying the
    schedule from the all-live initial state. Deterministic."""
    live = {n: True for n in nodes}
    for ev in schedule:
        if ev.t > t:
            break
        live[ev.node] = ev.kind == "spawn"
    return [n for n in nodes if live[n]]
