"""R6 — Multi-house federation + bridge node (measurement instrument).

Two federation modes, both built as *offline-verifiable logic* (no sockets, no
engine, no external target — containment stays law; this module moves no real
traffic and provides anonymity to no one, it only lets the study *measure* two
trust properties):

1. **directory-federation** (:class:`PeerRoster` / :class:`Directory`). Houses
   exchange a signed persona roster in a ``{"_sor":{"op":"peer",...}}`` HOUSE-PEER
   control frame (the same zero-knowledge-server-invisible channel R5 consent uses).
   A roster is Ed25519-signed by the announcing host and **rejected unless the
   signature verifies** (mirrors the R5 signature-gate discipline). A host merges
   validated rosters into a pubkey->house directory and builds a circuit that
   **spans >= 2 houses**, so no single house's node set covers every hop — the
   split-knowledge property the RQ2 acceptance check asserts ("no single node's
   logs contain all hop identities of a circuit").

2. **bridge-member** (:class:`BlindBridge`). A node that has joined two houses and
   **blind-forwards SOR tunnel bytes only**. It holds *no* room key for either
   house, so it structurally cannot read either room's chat plaintext — it relays
   opaque, already-onion-encrypted tunnel payloads verbatim and refuses (cannot
   open) anything else. Every relayed payload emits an R3 ``bridge_forward`` event
   (metadata only: circuit id, byte count — never plaintext).

Determinism comes from the R1 ``SorRng`` so a federated path is reproducible from
its seed alone. Signing/verification reuses the R5 persona primitives verbatim.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from cmd_chat.sor.config import Domain, SorRng
from cmd_chat.sor.consent import CONSENT_CTX, persona_sign, persona_verify
from cmd_chat.sor.events import EventLog

# HOUSE-PEER op value on the wire (the R5 frame parser already tags op=="peer").
PEER_OP = "peer"


# --------------------------------------------------------------------------- #
# directory-federation — signed persona roster exchange.
# --------------------------------------------------------------------------- #
def _roster_canonical(house_id: str, host_ed_pub: str, member_pubs: List[str]) -> bytes:
    """Canonical signed bytes for a roster. Members are sorted so the signature
    is order-independent (the roster is a *set* of pubkeys, not a sequence).
    Domain-separated with the shared CONSENT_CTX + a ``peer`` tag so a roster
    signature can never be replayed as a consent-request signature."""
    joined = ",".join(sorted(member_pubs))
    return (
        f"{CONSENT_CTX}\npeer\n{house_id}\n{host_ed_pub}\n{joined}"
    ).encode("utf-8")


@dataclass(frozen=True)
class PeerRoster:
    """A house's signed membership announcement: the announcing host's Ed25519
    pubkey, the house id, and the set of member persona pubkeys. Immutable."""

    house_id: str
    host_ed_pub: str
    member_pubs: Tuple[str, ...]
    sig: str

    def canonical(self) -> bytes:
        return _roster_canonical(self.house_id, self.host_ed_pub, list(self.member_pubs))

    def signature_ok(self) -> bool:
        """True iff the roster is validly signed by ``host_ed_pub``. A forged or
        unsigned roster is not ok — and is never merged into a directory."""
        return persona_verify(self.host_ed_pub, self.sig, self.canonical())


def build_peer_frame(
    host_secret_raw: bytes,
    host_ed_pub: str,
    house_id: str,
    member_pubs: List[str],
) -> str:
    """Build a signed HOUSE-PEER frame string ``{"_sor":{"op":"peer",...}}`` that
    announces ``house_id``'s roster, signed by the host's Ed25519 seed."""
    sig = persona_sign(host_secret_raw, _roster_canonical(house_id, host_ed_pub, member_pubs))
    return json.dumps(
        {
            "_sor": {
                "op": PEER_OP,
                "house": house_id,
                "host_ed": host_ed_pub,
                "roster": sorted(member_pubs),
                "sig": sig,
            }
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def parse_peer_frame(text: str) -> Optional[PeerRoster]:
    """Parse + verify a HOUSE-PEER frame into a :class:`PeerRoster`, or ``None``
    if it is not a recognized/valid peer frame. Never raises. Returns the roster
    only when its signature verifies — an unsigned/forged roster yields ``None``."""
    try:
        v = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(v, dict):
        return None
    inner = v.get("_sor")
    if not isinstance(inner, dict) or inner.get("op") != PEER_OP:
        return None
    house = inner.get("house")
    host_ed = inner.get("host_ed")
    roster = inner.get("roster")
    sig = inner.get("sig")
    if not (isinstance(house, str) and isinstance(host_ed, str) and isinstance(sig, str)):
        return None
    if not isinstance(roster, list) or not all(isinstance(p, str) for p in roster):
        return None
    r = PeerRoster(house, host_ed, tuple(roster), sig)
    return r if r.signature_ok() else None


class Directory:
    """A host-side pubkey -> house directory assembled from validated rosters.
    Only signature-verified rosters are admitted, so an unsigned/forged roster
    can never inject a node into a federated path."""

    def __init__(self) -> None:
        self._house_of: Dict[str, str] = {}       # member pubkey -> house_id
        self._members: Dict[str, List[str]] = {}   # house_id -> [pubkey,...]

    def add_roster(self, roster: PeerRoster) -> bool:
        """Merge a roster. Returns False (nothing merged) unless it verifies."""
        if not roster.signature_ok():
            return False
        members: List[str] = []
        for pub in roster.member_pubs:
            self._house_of[pub] = roster.house_id
            members.append(pub)
        self._members[roster.house_id] = members
        return True

    def houses(self) -> List[str]:
        return sorted(self._members)

    def members_of(self, house_id: str) -> List[str]:
        return list(self._members.get(house_id, []))

    def house_of(self, pub: str) -> Optional[str]:
        return self._house_of.get(pub)

    def select_federated_path(
        self, seed: int, hops: int = 3, min_houses: int = 2
    ) -> List[Tuple[str, str]]:
        """Deterministically pick ``hops`` distinct nodes spanning at least
        ``min_houses`` houses, returned as ``[(pubkey, house_id), ...]`` in circuit
        order. Draws from the R1 PATH stream so the path is reproducible from the
        seed. Raises ValueError if the directory can't satisfy the span (fewer
        than ``min_houses`` houses, or fewer than ``hops`` total nodes) — it does
        NOT silently collapse to a single-house path, because a single-house path
        would defeat the split-knowledge property this mode exists to measure."""
        houses = self.houses()
        if len(houses) < min_houses:
            raise ValueError(
                f"federation: need >= {min_houses} houses, have {len(houses)}"
            )
        total_nodes = sum(len(self._members[h]) for h in houses)
        if total_nodes < hops:
            raise ValueError(
                f"federation: need >= {hops} nodes across houses, have {total_nodes}"
            )

        s = SorRng(seed).stream(Domain.PATH)

        # Round-robin one node from each house first (guarantees the span), then
        # fill remaining hops from the combined remaining pool. Selection within
        # each pool is a deterministic PATH-stream draw.
        remaining: Dict[str, List[str]] = {h: list(self._members[h]) for h in houses}
        chosen: List[Tuple[str, str]] = []

        def _draw(house: str) -> None:
            pool = remaining[house]
            j = s.next_below(len(pool))
            pub = pool.pop(j)
            chosen.append((pub, house))

        # Guarantee the span: one hop from each of the first min_houses houses.
        for h in houses[:min_houses]:
            if len(chosen) >= hops:
                break
            _draw(h)

        # Fill the rest from whichever houses still have members.
        while len(chosen) < hops:
            avail = [h for h in houses if remaining[h]]
            if not avail:
                break
            h = avail[s.next_below(len(avail))]
            _draw(h)

        if len(chosen) < hops:
            raise ValueError("federation: exhausted node pool before filling path")
        return chosen


def path_span_ok(path: List[Tuple[str, str]], min_houses: int = 2) -> bool:
    """True iff ``path`` visits at least ``min_houses`` distinct houses — i.e. no
    single house appears at every hop, so no single house's logs hold all hop
    identities (the RQ2 split-knowledge acceptance predicate)."""
    return len({house for _, house in path}) >= min_houses


# --------------------------------------------------------------------------- #
# bridge-member — blind tunnel forwarder (no room key, plaintext-blind).
# --------------------------------------------------------------------------- #
def build_tunnel_frame(circuit_id: str, seq: int, onion_payload: bytes) -> str:
    """A SOR *tunnel* frame carrying already-onion-encrypted bytes (opaque to any
    bridge). This is the only thing a :class:`BlindBridge` will relay."""
    return json.dumps(
        {
            "_sor": {
                "op": "tunnel",
                "cid": circuit_id,
                "seq": seq,
                "payload_b64": base64.standard_b64encode(onion_payload).decode("ascii"),
            }
        },
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass
class BridgeForward:
    """Record of one blind relay: which circuit, byte count, direction. Metadata
    only — the bridge never holds or logs the payload plaintext."""

    circuit_id: str
    seq: int
    n_bytes: int
    src_house: str
    dst_house: str


class BlindBridge:
    """A bridge-member joined to two houses that relays SOR tunnel bytes and
    **nothing else**. It is constructed with *no* room key for either house, so it
    structurally cannot decrypt either room's chat plaintext: :meth:`forward`
    passes through only the opaque onion payload of a SOR ``tunnel`` frame and
    returns ``None`` for anything else (chat, consent, unknown) — a chat ciphertext
    handed to it stays sealed.

    Optionally emits an R3 ``bridge_forward`` event per relayed frame (metadata
    only), which is exactly what the RQ1 bridge-linkability measurement reads."""

    def __init__(self, house_a: str, house_b: str, log: Optional[EventLog] = None) -> None:
        self.house_a = house_a
        self.house_b = house_b
        self._log = log
        # A bridge holds NO room Fernet key — this is the load-bearing invariant.
        self.room_keys: Dict[str, object] = {}
        self.forwarded: List[BridgeForward] = []

    def has_room_key(self, house_id: str) -> bool:
        """Always False: a blind bridge is never given a room key, so it can never
        read chat plaintext. Exposed so the acceptance check can assert it."""
        return house_id in self.room_keys

    def _other(self, src_house: str) -> str:
        return self.house_b if src_house == self.house_a else self.house_a

    def forward(self, src_house: str, frame_text: str) -> Optional[bytes]:
        """Relay a frame arriving from ``src_house`` toward the other house.
        Returns the opaque onion payload bytes that were passed through (for a
        valid SOR ``tunnel`` frame), or ``None`` if the frame is not a tunnel
        frame — the bridge forwards nothing else and decrypts nothing. Never
        raises on arbitrary input."""
        try:
            v = json.loads(frame_text)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(v, dict):
            return None
        inner = v.get("_sor")
        if not isinstance(inner, dict) or inner.get("op") != "tunnel":
            # Chat frames, consent frames, unknown frames: the bridge cannot and
            # does not open them. Not a tunnel byte -> not forwarded.
            return None
        cid = inner.get("cid")
        seq = inner.get("seq")
        payload_b64 = inner.get("payload_b64")
        if not (isinstance(cid, str) and isinstance(seq, int) and isinstance(payload_b64, str)):
            return None
        try:
            payload = base64.standard_b64decode(payload_b64)
        except Exception:  # noqa: BLE001
            return None
        dst = self._other(src_house)
        self.forwarded.append(BridgeForward(cid, seq, len(payload), src_house, dst))
        if self._log is not None:
            self._log.emit(
                "bridge_forward",
                circuit_id=cid,
                hop_index=seq,
                bytes_=len(payload),
            )
        # Blind pass-through: the exact opaque bytes, never decrypted.
        return payload

    def try_read_chat(self, house_id: str, chat_ciphertext: bytes) -> Optional[bytes]:
        """Model the bridge attempting to read a room's chat plaintext. It holds
        no room key, so this always returns ``None`` — the bridge is plaintext-
        blind by construction. Present so the acceptance check can assert it."""
        return None
