"""Live per-cell condition assembler — turns a frozen §2 cell into a genuinely
distinct, ForwarderPlan-gated isolated circuit.

Each confirmatory cell is *not* the plain 3-hop control: this composes the
already-built R4/R5/R6 pieces so that a ``cell_id`` maps to a real circuit whose
**structure encodes its condition**, every hop gated by the R4 isolation guard
(:class:`ForwarderPlan`, ``assert engine != local``):

  * **RQ1 bridge=off** — a single-house 3-hop path (R1 ``select_path``).
  * **RQ1 bridge=on** — the middle hop is a **bridge** node (R6 ``BlindBridge``
    role), so the circuit is routed through a bridge; structurally distinct.
  * **RQ1 bridge=on+padding** — bridge on, plus the R1 PADDING stream drives
    cover traffic on the path (``padding_applied``).
  * **RQ2 1house-N** — single house sized to the **matched-N** node count.
  * **RQ2 bridge-federated** — entry/exit in *different* houses joined by a
    ``BlindBridge`` member: the path spans ≥ 2 houses.
  * **RQ2 directory-federated** — a signed-roster :class:`Directory` and
    ``select_federated_path`` pick a path spanning ≥ 2 houses (split knowledge).

Determinism comes from the R1 ``SorRng`` / frozen seed so the same ``(cell,
seed)`` reproduces the same circuit; different cells produce different circuits.
This module builds **plans only** — it opens no socket, moves no traffic, and
stands up no engine. The live traffic that would consume these plans is the
human-gated confirmatory data run (``confirmatory_run``); here we only validate,
on fixtures, that each cell is a real, distinct, isolated-engine circuit.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cmd_chat.sor.config import SorRng, select_path
from cmd_chat.sor.consent import _fingerprint_of, persona_sign
from cmd_chat.sor.federation import Directory, build_peer_frame, parse_peer_frame
from cmd_chat.sor.forwarder import ContainmentError, ForwarderPlan

HOUSES = ("houseA", "houseB")
DEFAULT_HOUSE_SIZE = 4
DEFAULT_N_HOUSES = 2
DEFAULT_HOPS = 3


@dataclass(frozen=True)
class HopSpec:
    """One hop of an assembled circuit. ``is_bridge`` marks the R6 bridge role."""

    index: int
    role: str            # "entry" | "relay" | "exit" | "bridge"
    house: str
    node_label: str      # deterministic node identity (fingerprint or house#idx)
    is_bridge: bool


@dataclass(frozen=True)
class CircuitSpec:
    """A fully-determined, condition-encoding circuit for one cell. Immutable; its
    :meth:`plans` are the R4 isolation-gated forwarder targets."""

    cell_id: str
    rq: str
    seed: int
    engine: str
    topology: str
    bridge_present: bool
    padding_applied: bool
    matched_n: int
    houses: Tuple[str, ...]
    hops: Tuple[HopSpec, ...]

    def _semantic(self) -> Dict:
        """The condition-defining content (no container names — those derive from
        this), so the fingerprint reflects the *circuit*, not incidental naming."""
        return {
            "cell_id": self.cell_id, "rq": self.rq, "seed": self.seed,
            "topology": self.topology, "bridge_present": self.bridge_present,
            "padding_applied": self.padding_applied, "matched_n": self.matched_n,
            "houses": list(self.houses),
            "hops": [[h.index, h.role, h.house, h.node_label, h.is_bridge]
                     for h in self.hops],
        }

    def fingerprint(self) -> str:
        """SHA-256 over the semantic content. Same (cell, seed) → same fingerprint
        (reproducible); different cells → different fingerprints (distinct)."""
        blob = json.dumps(self._semantic(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def container_name(self, i: int) -> str:
        return f"sorcell-{self.fingerprint()[:8]}-h{i}"

    def plans(self) -> List[ForwarderPlan]:
        """The R4 isolation-gated forwarder target for each hop. Building a plan
        re-asserts ``engine != local`` — a non-isolated engine raises here."""
        return [ForwarderPlan(engine=self.engine, container=self.container_name(h.index))
                for h in self.hops]

    def isolation_gated(self) -> bool:
        """True iff every hop builds a valid isolated ForwarderPlan (containment)."""
        try:
            self.plans()
            return True
        except ContainmentError:
            return False

    def span_houses(self) -> int:
        return len({h.house for h in self.hops})

    def to_dict(self) -> Dict:
        d = self._semantic()
        d["fingerprint"] = self.fingerprint()
        d["engine"] = self.engine
        d["span_houses"] = self.span_houses()
        d["isolation_gated"] = self.isolation_gated()
        return d


def _persona(seed: int, tag: str) -> Tuple[bytes, str]:
    """A deterministic fixture Ed25519 keypair as (secret_raw, pub_b64)."""
    raw = hashlib.sha256(f"sor-persona|{seed}|{tag}".encode()).digest()[:32]
    sk = Ed25519PrivateKey.from_private_bytes(raw)
    pub = base64.standard_b64encode(sk.public_key().public_bytes_raw()).decode()
    return raw, pub


def _bridge_label(seed: int) -> str:
    return f"bridge#{hashlib.sha256(f'sor-bridge|{seed}'.encode()).hexdigest()[:8]}"


def zipf_weights(pool_size: int, alpha: float) -> List[float]:
    """Deterministic Zipf willingness weights over a finite willing-bridge POOL of
    ``pool_size`` bridges: rank ``r`` (1..B) gets mass ∝ ``1/r**alpha``, normalized to
    sum 1. ``alpha = 0`` → uniform willingness; larger ``alpha`` → heavier skew toward
    the most-willing bridges (higher realized concentration). Pure function of
    ``(pool_size, alpha)`` — both cell-level factors — so the willingness profile is
    fixed within a run (RQ2-P3 mechanism prereg §3)."""
    if pool_size < 1:
        raise ValueError(f"pool_size must be >= 1, got {pool_size}")
    raw = [1.0 / (r ** alpha) for r in range(1, pool_size + 1)]
    total = sum(raw)
    return [w / total for w in raw]


def weighted_draw(digest_hex: str, weights: List[float]) -> int:
    """Deterministic index in ``[0, len(weights))`` by CDF inversion of a SHA-256
    hex digest: the first 8 bytes map to ``u ∈ [0, 1)`` and we return the first bin
    whose cumulative weight exceeds ``u``. Deterministic from ``digest_hex`` (a
    per-circuit hash), so a circuit's willing bridge is reproducible from its seed."""
    if not weights:
        raise ValueError("weights must be non-empty")
    u = int(digest_hex[:16], 16) / float(1 << 64)
    cum = 0.0
    for i, w in enumerate(weights):
        cum += w
        if u < cum:
            return i
    return len(weights) - 1


def _house_nodes(seed: int, pool: int, take: int, house: str, salt: int = 0) -> List[str]:
    idx = select_path(SorRng(seed ^ salt), pool, take)
    return [f"{house}#{i}" for i in idx]


def _build_directory(seed: int, house_size: int, n_houses: int) -> Directory:
    """A signature-verified directory over ``n_houses`` fixture houses so
    ``select_federated_path`` can span ≥ 2 of them (roster forgery is refused)."""
    d = Directory()
    for house in HOUSES[:n_houses]:
        host_secret, host_pub = _persona(seed, f"host|{house}")
        members = [_persona(seed, f"{house}|m{m}")[1] for m in range(house_size)]
        frame = build_peer_frame(host_secret, host_pub, house, members)
        roster = parse_peer_frame(frame)   # verifies the signature
        if roster is None or not d.add_roster(roster):
            raise ValueError(f"assembler: fixture roster for {house} failed to verify")
    return d


def assemble(
    cell, seed: int, *, engine: str = "docker",
    hops: int = DEFAULT_HOPS, house_size: int = DEFAULT_HOUSE_SIZE,
    n_houses: int = DEFAULT_N_HOUSES,
) -> CircuitSpec:
    """Assemble the genuinely distinct, isolation-gated circuit for ``cell`` at
    ``seed``. Dispatches on the frozen §2 factors (bridge / topology). Raises
    ValueError if a federated cell cannot honour its ≥2-house span."""
    bridge = cell.factors.get("bridge", "off")
    topo = cell.factors.get("topology", "1house")
    matched_n = house_size * n_houses  # federated arm's total consenting nodes

    hop_specs: List[HopSpec]
    houses: Tuple[str, ...]
    bridge_present = False
    padding_applied = False

    if cell.rq == "RQ1":
        houses = (HOUSES[0],)
        if bridge == "off":
            labels = _house_nodes(seed, house_size, hops, HOUSES[0])
            roles = ["entry", "relay", "exit"][:hops]
            hop_specs = [HopSpec(i, roles[i], HOUSES[0], labels[i], False)
                         for i in range(hops)]
        else:  # "on" or "on+padding": route the middle hop through a bridge node.
            ends = _house_nodes(seed, house_size, 2, HOUSES[0])
            hop_specs = [
                HopSpec(0, "entry", HOUSES[0], ends[0], False),
                HopSpec(1, "bridge", "bridge", _bridge_label(seed), True),
                HopSpec(2, "exit", HOUSES[0], ends[1], False),
            ]
            bridge_present = True
            padding_applied = (bridge == "on+padding")
    else:  # RQ2 — bridge always off; the topology factor varies.
        if topo == "1house-N":
            houses = (HOUSES[0],)
            labels = _house_nodes(seed, matched_n, hops, HOUSES[0])
            roles = ["entry", "relay", "exit"][:hops]
            hop_specs = [HopSpec(i, roles[i], HOUSES[0], labels[i], False)
                         for i in range(hops)]
        elif topo == "bridge-federated":
            a = _house_nodes(seed, house_size, 1, HOUSES[0], salt=0)[0]
            b = _house_nodes(seed, house_size, 1, HOUSES[1], salt=0xB)[0]
            hop_specs = [
                HopSpec(0, "entry", HOUSES[0], a, False),
                HopSpec(1, "bridge", "bridge", _bridge_label(seed), True),
                HopSpec(2, "exit", HOUSES[1], b, False),
            ]
            houses = (HOUSES[0], HOUSES[1])
            bridge_present = True
        elif topo == "bridge-federated-pool":
            # RQ2-P3 mechanism instrument (rq2p3-mechanism-prereg.md §3): identical
            # to bridge-federated EXCEPT the willing bridge is drawn from a FINITE
            # shared pool of size B under a fixed Zipf willingness (skew alpha), so
            # circuits genuinely REUSE bridges and top-3 concentration varies. The
            # existing bridge-federated branch above is left untouched (lead cells
            # stay bit-reproducible).
            pool_b = int(cell.factors["pool_B"])
            pool_alpha = float(cell.factors["pool_alpha"])
            a = _house_nodes(seed, house_size, 1, HOUSES[0], salt=0)[0]
            b = _house_nodes(seed, house_size, 1, HOUSES[1], salt=0xB)[0]
            weights = zipf_weights(pool_b, pool_alpha)
            digest = hashlib.sha256(f"sor-bridge-pool|{seed}".encode()).hexdigest()
            idx = weighted_draw(digest, weights)
            hop_specs = [
                HopSpec(0, "entry", HOUSES[0], a, False),
                HopSpec(1, "bridge", "bridge", f"bridge#{idx:02d}", True),
                HopSpec(2, "exit", HOUSES[1], b, False),
            ]
            houses = (HOUSES[0], HOUSES[1])
            bridge_present = True
        elif topo == "directory-federated":
            directory = _build_directory(seed, house_size, n_houses)
            path = directory.select_federated_path(seed, hops=hops, min_houses=2)
            roles = ["entry", "relay", "exit"][:hops]
            hop_specs = [HopSpec(i, roles[i], house, _fingerprint_of(pub), False)
                         for i, (pub, house) in enumerate(path)]
            houses = tuple(sorted({h.house for h in hop_specs}))
        else:
            raise ValueError(f"assembler: unknown RQ2 topology {topo!r}")

    spec = CircuitSpec(
        cell_id=cell.cell_id, rq=cell.rq, seed=seed, engine=engine,
        topology=topo, bridge_present=bridge_present, padding_applied=padding_applied,
        matched_n=matched_n, houses=houses, hops=tuple(hop_specs),
    )
    # Federated cells must genuinely span ≥ 2 houses (split-knowledge, RQ2).
    if topo in ("bridge-federated", "bridge-federated-pool", "directory-federated") and spec.span_houses() < 2:
        raise ValueError(f"assembler: {cell.cell_id} failed the >=2-house span")
    return spec


def assemble_all(cells, run_index: int = 0, *, engine: str = "docker") -> Dict[str, CircuitSpec]:
    """Assemble one representative circuit per cell (at ``run_index``) using the
    frozen seed rule. Returns ``cell_id -> CircuitSpec``."""
    from cmd_chat.sor.battery import derive_seed

    return {c.cell_id: assemble(c, derive_seed(c.cell_id, run_index), engine=engine)
            for c in cells}
