"""R7 — Path selector that rebuilds circuits under churn.

The selector consumes a churn schedule (``churn.py``) and, whenever a live circuit
loses a node to a kill, **rebuilds** it from the currently-live pool. The rebuild
decision is a pluggable :class:`SelectorPolicy` so the RQ3 arms can be swapped
without touching the replay loop. Three built-in strategies, all deterministic
and offline:

  * ``static``  — canonical-order pick (stable, no randomness);
  * ``random``  — seeded SELECTOR-stream pick from the live pool;
  * ``agent``   — an agent policy. The default backend is a *local* stability
    heuristic (prefers nodes that have churned least). A reproducible
    local-open-source-model backend (Ollama, temp=0, seed-pinned, decision-cached)
    lives in ``agent_selector.py`` and is selected with ``agent_backend="ollama"``.
    The paid frontier-model / Claude Code arm is **human + budget gated** (GOAL
    autonomy envelope (c)) and is only exposed as an EXPLORATORY stub that makes
    no external call — it is never wired as a confirmatory arm here.

The R7 acceptance predicate this satisfies: under a fixed churn seed the selector
rebuilds every dropped circuit (as long as the live pool can supply ``hops``
nodes). Rebuild activity is emitted as R3 ``rebuild_start``/``rebuild_done`` +
``churn_kill``/``churn_spawn`` events when an :class:`EventLog` is supplied.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from cmd_chat.sor.churn import ChurnEvent
from cmd_chat.sor.config import Domain, SorRng
from cmd_chat.sor.events import EventLog

STRATEGIES = ("static", "random", "agent")
AGENT_BACKENDS = ("heuristic", "ollama", "claude")


# --------------------------------------------------------------------------- #
# Pluggable selection policy — the RQ3 arm seam.
# --------------------------------------------------------------------------- #
@dataclass
class SelectorContext:
    """State a policy may read when choosing a circuit. ``kill_counts`` is the
    running per-node churn history; ``draws`` advances a random stream across
    rebuilds so a stochastic policy stays deterministic within a run."""

    seed: int
    hops: int
    kill_counts: Dict[str, int] = field(default_factory=dict)
    draws: int = 0


class SelectorPolicy(ABC):
    """Chooses a ``hops``-length circuit from a live pool. Implementations must be
    deterministic given ``(live, ctx)`` so a run is reproducible from its seed."""

    name: str = "policy"

    @abstractmethod
    def choose(self, live: List[str], ctx: SelectorContext) -> Optional[List[str]]:
        """Return a ``ctx.hops``-length circuit of distinct nodes drawn from
        ``live``, or ``None`` if the pool is too small."""

    def provenance(self) -> Dict[str, Any]:
        """Auditable description of this policy for the run manifest sidecar."""
        return {"policy": self.name}


class StaticPolicy(SelectorPolicy):
    name = "static"

    def choose(self, live: List[str], ctx: SelectorContext) -> Optional[List[str]]:
        if len(live) < ctx.hops:
            return None
        return sorted(live)[: ctx.hops]


class RandomPolicy(SelectorPolicy):
    name = "random"

    def choose(self, live: List[str], ctx: SelectorContext) -> Optional[List[str]]:
        if len(live) < ctx.hops:
            return None
        work = sorted(live)
        s = SorRng(ctx.seed).stream(Domain.SELECTOR)
        for _ in range(ctx.draws):  # replay to current position (determinism)
            s.next_u64()
        picked: List[str] = []
        for _ in range(ctx.hops):
            j = s.next_below(len(work))
            picked.append(work.pop(j))
            ctx.draws += 1
        return picked


class HeuristicAgentPolicy(SelectorPolicy):
    """Local, model-free agent stand-in: prefer the nodes that have churned least
    (fewest kills), ties broken by id. Spends nothing, calls nothing."""

    name = "agent-heuristic"

    def choose(self, live: List[str], ctx: SelectorContext) -> Optional[List[str]]:
        if len(live) < ctx.hops:
            return None
        ranked = sorted(live, key=lambda n: (ctx.kill_counts.get(n, 0), n))
        return ranked[: ctx.hops]


def make_policy(strategy: str, agent_backend: str = "heuristic", **kwargs: Any) -> SelectorPolicy:
    """Resolve a ``(strategy, agent_backend)`` pair to a concrete policy. The
    ``ollama``/``claude`` agent backends are imported lazily so the base selector
    carries no network/model dependency."""
    if strategy == "static":
        return StaticPolicy()
    if strategy == "random":
        return RandomPolicy()
    if strategy == "agent":
        if agent_backend == "heuristic":
            return HeuristicAgentPolicy()
        if agent_backend == "ollama":
            from cmd_chat.sor.agent_selector import OllamaAgentPolicy
            return OllamaAgentPolicy(**kwargs)
        if agent_backend == "claude":
            from cmd_chat.sor.agent_selector import ClaudeExploratoryPolicy
            return ClaudeExploratoryPolicy(**kwargs)
        raise ValueError(f"unknown agent backend {agent_backend!r} (of {AGENT_BACKENDS})")
    raise ValueError(f"unknown selector strategy {strategy!r} (of {STRATEGIES})")


@dataclass
class Rebuild:
    """One rebuild triggered by a drop: the step, the node that dropped, and the
    replacement circuit (node ids in order)."""

    t: int
    dropped: str
    circuit: List[str]


@dataclass
class SelectionResult:
    """Outcome of replaying a churn schedule under a selector strategy."""

    strategy: str
    seed: int
    hops: int
    initial_circuit: List[str]
    rebuilds: List[Rebuild] = field(default_factory=list)
    drops: int = 0
    deferred: int = 0  # drops that could not be rebuilt (pool < hops at that step)
    events_sha256: Optional[str] = None
    policy_provenance: Optional[Dict[str, Any]] = None

    @property
    def every_drop_rebuilt(self) -> bool:
        """True iff every drop that broke the circuit was met by a rebuild — the
        R7 acceptance predicate (no deferred/unhealed drops)."""
        return self.deferred == 0 and len(self.rebuilds) == self.drops


class Selector:
    """Picks a ``hops``-length circuit from a live pool via a pluggable
    :class:`SelectorPolicy`. Pure and deterministic; the same (seed, policy, live
    pool, churn history) always yields the same circuit."""

    def __init__(
        self,
        strategy: str,
        seed: int,
        hops: int,
        *,
        agent_backend: str = "heuristic",
        policy: Optional[SelectorPolicy] = None,
        **policy_kwargs: Any,
    ) -> None:
        if policy is not None:
            self._policy = policy
            self.strategy = getattr(policy, "name", "custom")
        else:
            self._policy = make_policy(strategy, agent_backend, **policy_kwargs)
            self.strategy = strategy
        self.seed = seed
        self.hops = hops
        self._ctx = SelectorContext(seed=seed, hops=hops)

    @property
    def policy(self) -> SelectorPolicy:
        return self._policy

    def note_kill(self, node: str) -> None:
        self._ctx.kill_counts[node] = self._ctx.kill_counts.get(node, 0) + 1

    def build(self, live: List[str]) -> Optional[List[str]]:
        """Return a ``hops``-length circuit from ``live``, or ``None`` if the pool
        is too small (fewer than ``hops`` live nodes)."""
        return self._policy.choose(list(live), self._ctx)


def run_selection(
    seed: int,
    nodes: List[str],
    hops: int,
    schedule: List[ChurnEvent],
    strategy: str = "static",
    log: Optional[EventLog] = None,
    *,
    agent_backend: str = "heuristic",
    policy: Optional[SelectorPolicy] = None,
    run_dir: Optional[Path] = None,
    **policy_kwargs: Any,
) -> SelectionResult:
    """Replay ``schedule`` over ``nodes`` under ``strategy`` and rebuild the circuit
    whenever a kill drops one of its nodes. Deterministic from the inputs.

    Returns a :class:`SelectionResult`; ``result.every_drop_rebuilt`` is the R7
    acceptance predicate. If ``log`` is given, emits R3 churn/rebuild events. If
    ``run_dir`` is given, writes the policy provenance (model id/digest, decision
    cache) to ``selector.json`` so an agent-backed run is auditable + replayable."""
    sel = Selector(strategy, seed, hops, agent_backend=agent_backend,
                   policy=policy, **policy_kwargs)
    live = {n: True for n in nodes}
    live_list = [n for n in nodes if live[n]]
    initial = sel.build(live_list) or []
    circuit: List[str] = list(initial)
    result = SelectionResult(sel.strategy, seed, hops, list(initial))

    for ev in schedule:
        if ev.kind == "kill":
            live[ev.node] = False
            sel.note_kill(ev.node)
            if log is not None:
                log.emit("churn_kill", node_fp=_fp(ev.node), hop_index=ev.t)
            if ev.node in circuit:
                # The live circuit lost a hop -> must rebuild.
                result.drops += 1
                if log is not None:
                    log.emit("rebuild_start", circuit_id=f"t{ev.t}", hop_index=ev.t)
                rebuilt = sel.build([n for n in nodes if live[n]])
                if rebuilt is None:
                    result.deferred += 1  # pool too small right now
                    circuit = []
                else:
                    circuit = rebuilt
                    result.rebuilds.append(Rebuild(ev.t, ev.node, list(rebuilt)))
                    if log is not None:
                        log.emit("rebuild_done", circuit_id=f"t{ev.t}",
                                 hop_index=len(rebuilt))
        else:  # spawn
            live[ev.node] = True
            if log is not None:
                log.emit("churn_spawn", node_fp=_fp(ev.node), hop_index=ev.t)
            if not circuit:
                # A deferred drop can now be healed once the pool recovers.
                rebuilt = sel.build([n for n in nodes if live[n]])
                if rebuilt is not None:
                    circuit = rebuilt
                    result.deferred = max(0, result.deferred - 1)
                    result.rebuilds.append(Rebuild(ev.t, ev.node, list(rebuilt)))
                    if log is not None:
                        log.emit("rebuild_done", circuit_id=f"t{ev.t}",
                                 hop_index=len(rebuilt))

    if log is not None:
        result.events_sha256 = log.close()

    result.policy_provenance = sel.policy.provenance()
    if run_dir is not None:
        _write_selector_sidecar(Path(run_dir), sel, result)
    return result


def _write_selector_sidecar(run_dir: Path, sel: "Selector", result: SelectionResult) -> Path:
    """Persist the policy provenance (+ any decision cache) to ``selector.json`` —
    a write-once, hashable audit artifact folding the agent backend into the run's
    provenance (model id/digest, per-state decisions)."""
    import json

    run_dir.mkdir(parents=True, exist_ok=True)
    doc: Dict[str, Any] = {
        "strategy": result.strategy,
        "seed": result.seed,
        "hops": result.hops,
        "provenance": result.policy_provenance,
    }
    decisions = getattr(sel.policy, "decisions", None)
    if callable(decisions):
        doc["decisions"] = decisions()
    path = run_dir / "selector.json"
    if path.exists():
        raise FileExistsError(f"selector.json already exists (immutable): {path}")
    path.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def _fp(node: str) -> str:
    """A short, stable fingerprint of a node id for event metadata (never the id
    verbatim in case ids ever carry structure)."""
    import hashlib

    return hashlib.sha256(node.encode("utf-8")).hexdigest()[:8]
