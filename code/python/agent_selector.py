"""R7 — Agent selector backends (RQ3 treatment arm).

Two backends plug into the :class:`~cmd_chat.sor.selector.SelectorPolicy` seam:

* :class:`OllamaAgentPolicy` — the **reproducible confirmatory** agent arm. It
  asks a *local, open-source* model (served by Ollama on localhost) to rank the
  live pool and pick a rebuild circuit. Reproducibility is engineered in, not
  hoped for:
    - inference is pinned (``temperature=0`` + per-run ``seed``);
    - every decision is **cached keyed by (seed, state-hash)**, so a replay is
      byte-identical regardless of any model nondeterminism;
    - any model/parse/validation failure falls back to the deterministic local
      heuristic, so a run never breaks and never silently drifts;
    - the model id + weights **digest** are recorded for the provenance manifest.
  This is a *local* call to ``localhost:11434`` — no external target, no relay
  traffic; it is a measurement decision, not part of the data plane.

* :class:`ClaudeExploratoryPolicy` — an **EXPLORATORY-only** hook for a Claude
  Code / frontier arm. It is deliberately inert: it makes **no paid model call**
  and refuses to run as a confirmatory backend (the paid frontier arm is human +
  budget gated, GOAL autonomy envelope (c)). It exists so the seam is documented,
  not so it can spend.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from cmd_chat.sor.selector import HeuristicAgentPolicy, SelectorContext, SelectorPolicy

DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_HOST = "http://localhost:11434"


def _state_hash(live: List[str], ctx: SelectorContext) -> str:
    """A stable hash of the decision state — the same live pool + churn history +
    seed + hops always hashes identically, so it is a sound cache key."""
    blob = json.dumps(
        {
            "seed": ctx.seed,
            "hops": ctx.hops,
            "live": sorted(live),
            "kills": {n: ctx.kill_counts.get(n, 0) for n in sorted(live)},
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class OllamaAgentPolicy(SelectorPolicy):
    """Local-OSS-model rebuild policy (reproducible confirmatory agent arm)."""

    name = "agent-ollama"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        timeout: float = 30.0,
        cache: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self._cache: Dict[str, List[str]] = cache if cache is not None else {}
        self._fallback = HeuristicAgentPolicy()
        self._model_digest: Optional[str] = None
        self._digest_resolved = False
        self._decisions: List[Dict[str, Any]] = []

    # -- provenance ------------------------------------------------------- #
    def _resolve_digest(self) -> Optional[str]:
        """Best-effort: fetch the model's content digest from Ollama so the exact
        weights are pinned into the run manifest. Never raises."""
        if self._digest_resolved:
            return self._model_digest
        self._digest_resolved = True
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                tags = json.loads(resp.read().decode("utf-8"))
            for m in tags.get("models", []):
                if m.get("name") == self.model or m.get("model") == self.model:
                    self._model_digest = m.get("digest")
                    break
        except Exception:  # noqa: BLE001
            self._model_digest = None
        return self._model_digest

    def provenance(self) -> Dict[str, Any]:
        n_model = sum(1 for d in self._decisions if d.get("source") == "model")
        n_cache = sum(1 for d in self._decisions if d.get("source") == "cache")
        n_fallback = sum(1 for d in self._decisions if d.get("source") == "fallback")
        return {
            "policy": self.name,
            "model": self.model,
            "model_digest": self._resolve_digest(),
            "host": self.host,
            "options": {"temperature": 0, "seed": "per-run", "format": "json"},
            "decisions": {
                "total": len(self._decisions),
                "model": n_model,
                "cache": n_cache,
                "fallback": n_fallback,
            },
        }

    def decisions(self) -> List[Dict[str, Any]]:
        """The per-state decision log (state-hash, chosen circuit, source) — folded
        into the run provenance sidecar so an agent run is fully auditable."""
        return list(self._decisions)

    # -- decision --------------------------------------------------------- #
    def choose(self, live: List[str], ctx: SelectorContext) -> Optional[List[str]]:
        if len(live) < ctx.hops:
            return None
        key = f"{ctx.seed}:{_state_hash(live, ctx)}"
        if key in self._cache:
            chosen = list(self._cache[key])
            self._decisions.append({"state": key, "chosen": chosen, "source": "cache"})
            return chosen

        chosen = self._query_model(live, ctx)
        source = "model"
        if not self._valid(chosen, live, ctx.hops):
            chosen = self._fallback.choose(live, ctx)  # deterministic, never breaks
            source = "fallback"
        assert chosen is not None  # pool>=hops guaranteed above
        self._cache[key] = list(chosen)
        self._decisions.append({"state": key, "chosen": list(chosen), "source": source})
        return list(chosen)

    def _valid(self, chosen: Optional[List[str]], live: List[str], hops: int) -> bool:
        if not isinstance(chosen, list) or len(chosen) != hops:
            return False
        if len(set(chosen)) != hops:
            return False
        pool = set(live)
        return all(isinstance(c, str) and c in pool for c in chosen)

    def _query_model(self, live: List[str], ctx: SelectorContext) -> Optional[List[str]]:
        """Ask the local model for a rebuild circuit. Returns a list of node ids or
        ``None`` on any transport/parse failure (caller falls back)."""
        prompt = self._build_prompt(live, ctx)
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0, "seed": ctx.seed, "num_predict": 160},
            }
        ).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{self.host}/api/generate", data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            text = body.get("response", "")
            parsed = json.loads(text)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            return None
        except Exception:  # noqa: BLE001 — never let the model break a run
            return None
        # Accept {"circuit":[...]} or a bare [...].
        if isinstance(parsed, dict):
            parsed = parsed.get("circuit") or parsed.get("nodes")
        if not isinstance(parsed, list):
            return None
        return [str(x) for x in parsed][: ctx.hops]

    def _build_prompt(self, live: List[str], ctx: SelectorContext) -> str:
        kills = {n: ctx.kill_counts.get(n, 0) for n in sorted(live)}
        return (
            "You are a path selector for a research relay measurement. Choose the "
            f"{ctx.hops} most churn-stable nodes to rebuild a circuit. A node that "
            "has been killed more often is less stable; prefer fewer past kills, "
            "break ties by node id ascending. Return ONLY strict JSON of the form "
            '{"circuit": ["<id>", ...]} with exactly '
            f"{ctx.hops} distinct ids chosen from the candidate pool.\n"
            f"Candidate pool (id: past_kills): {json.dumps(kills, sort_keys=True)}\n"
        )


class ClaudeExploratoryPolicy(SelectorPolicy):
    """EXPLORATORY-only Claude Code / frontier hook. Inert by design: it makes NO
    paid model call and cannot serve as a confirmatory arm. The paid frontier arm
    is human + budget gated (GOAL autonomy envelope (c)); wiring it live is a
    deliberate, separately-authorized step — not something this build performs."""

    name = "agent-claude-exploratory"

    def __init__(self, allow_exploratory: bool = False) -> None:
        self.allow_exploratory = allow_exploratory

    def choose(self, live: List[str], ctx: SelectorContext) -> Optional[List[str]]:
        raise NotImplementedError(
            "Claude Code agent arm is EXPLORATORY-only and is not wired for "
            "confirmatory runs: no paid-model call is made in this build (GOAL "
            "envelope (c), human + budget gated). Use agent_backend='ollama' for "
            "the reproducible local-model arm."
        )

    def provenance(self) -> Dict[str, Any]:
        return {
            "policy": self.name,
            "status": "exploratory-stub",
            "paid_calls": False,
            "wired": False,
        }
