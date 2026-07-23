"""R4 — SSH-tunnel data plane (nested-circuit forwarder), isolated-engine-only.

Two parts, both gated by the same containment invariant (``assert engine !=
local`` or refuse):

1. **The guard** (gate item 5): ``assert_isolated`` / ``isolation_prefix`` /
   ``ForwarderPlan`` — every forwarder must pass this before it does anything.
   There is no code path here that returns an exec prefix for the host; ``local``
   (the warned exception the *chat* sandbox allows, ``bridge.py:540``) is never
   valid for a SOR run. This half is fully verifiable offline.

2. **The e2e circuit runner** (gate item 1): ``run_circuit_fixture`` stands up an
   ``N``-hop nested-SSH chain of isolated **docker** containers, pipes a
   seed-deterministic *self-generated* payload through it, captures a per-hop
   pcap, verifies end-to-end delivery, checksums each pcap, emits R3 events, and
   tears the circuit down. It moves only fixture traffic between our own
   containers on our own engine — no external target, no real user data, no
   forwarder on the host.

Containment (CLAUDE.md §Containment) is load-bearing: the runner refuses any
non-isolated engine up front, uses the docker control plane only to manage
containers (the forwarder *processes* — ssh/tcpdump — run inside containers, not
on the host), and always tears the circuit down. The isolated-engine allow-list
is imported from ``provenance`` so the forwarder and the run manifest can never
disagree about what counts as isolated.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cmd_chat.sor.config import Domain, SorRng
from cmd_chat.sor.events import EventLog
from cmd_chat.sor.provenance import ISOLATED_ENGINES

# The host. Never a valid engine for a SOR forwarder — its whole purpose is to
# keep every forwarder/circuit process off the host (blast-radius containment).
LOCAL_ENGINE = "local"


class ContainmentError(RuntimeError):
    """A forwarder was asked to run on a non-isolated engine (or with no
    container/VM to exec into). Raised instead of running — the code refuses."""


def assert_isolated(engine: str) -> None:
    """Raise :class:`ContainmentError` unless ``engine`` is an isolated engine.

    This is the ``assert engine != local`` half of the R4 acceptance check
    (instrument-validation gate item 5), hardened to also reject any engine not
    on the manifest allow-list (unknown engines are refused, not assumed safe)."""
    if engine == LOCAL_ENGINE:
        raise ContainmentError(
            "containment: SOR forwarders never run on the host "
            f"({LOCAL_ENGINE!r}); isolated engine required (one of {ISOLATED_ENGINES})"
        )
    if engine not in ISOLATED_ENGINES:
        raise ContainmentError(
            f"containment: engine {engine!r} is not an isolated engine "
            f"(allowed: {ISOLATED_ENGINES})"
        )


def isolation_prefix(engine: str, container: str) -> List[str]:
    """The argv prefix that runs a command *inside* the named isolated engine —
    the same shape the chat sandbox uses (``bridge.py:_exec_prefix``), minus the
    ``local`` host exception, which is refused here. The caller appends the actual
    program + args as separate argv items (never a shell-interpolated string), so
    circuit descriptors can't inject shell metacharacters.

    Refuses (raises) on a non-isolated engine or a missing container name."""
    assert_isolated(engine)
    if not container:
        raise ContainmentError(
            f"containment: no container/VM name to exec into for engine {engine!r}"
        )
    if engine == "docker":
        return ["docker", "exec", "-i", container]
    if engine == "multipass":
        return ["multipass", "exec", container, "--"]
    # Unreachable: assert_isolated already constrained `engine` to ISOLATED_ENGINES
    # and both members are handled above. Refuse rather than fall through silently.
    raise ContainmentError(f"containment: no isolation prefix for engine {engine!r}")


@dataclass(frozen=True)
class ForwarderPlan:
    """A validated, inert description of *where* a hop forwarder would run. Its
    construction is the containment gate: a plan for a ``local``/unknown engine,
    or with no container, cannot be built. It carries no credentials, opens no
    connection, and moves no bytes — the traffic-moving forwarder that would
    consume it (gate item 1) is HELD for the human + a live grid."""

    engine: str
    container: str

    def __post_init__(self) -> None:
        assert_isolated(self.engine)
        if not self.container:
            raise ContainmentError(
                f"containment: no container/VM name for engine {self.engine!r}"
            )

    def exec_prefix(self) -> List[str]:
        """The isolated exec argv prefix for this plan (validated at build time)."""
        return isolation_prefix(self.engine, self.container)


# --------------------------------------------------------------------------- #
# The e2e circuit runner (gate item 1).
#
# Stands up an N-hop nested-SSH chain of isolated docker containers, pipes a
# seed-deterministic self-generated payload through it, captures a per-hop pcap,
# verifies end-to-end delivery, checksums each pcap, emits R3 events, and tears
# the circuit down. Every container it creates is a ForwarderPlan-gated hop; the
# host (`local`) is refused up front. Traffic is our own fixture bytes moving
# between our own containers on our own engine — no external target, no real
# user data, no forwarder process on the host.
# --------------------------------------------------------------------------- #

# The fixture relay image (built from fixtures/hop.Dockerfile): alpine + sshd +
# openssh-client + tcpdump. Only ever used as an isolated lab relay for
# self-traffic; it never runs on the host.
HOP_IMAGE = "sor-hop:latest"

# ssh hardening applied inside the *client* container only (never the host): the
# lab hops use throwaway host keys, so the client accepts-on-first-use and keeps
# no known_hosts. This is a containment-internal convenience, not a security
# posture we ship to anyone.
_CLIENT_SSH_CONFIG = (
    "Host *\n"
    "    StrictHostKeyChecking accept-new\n"
    "    UserKnownHostsFile /dev/null\n"
    "    LogLevel ERROR\n"
)


class CircuitError(RuntimeError):
    """The e2e circuit could not be stood up, delivered, or verified. Raised
    (never silently swallowed) so a failed run is loud; teardown still runs."""


def _docker(*args: str, check: bool = True, capture: bool = True,
            input_bytes: Optional[bytes] = None, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a single `docker ...` control-plane command. Args are passed as
    separate argv items (never a shell string) so container/circuit names can't
    inject shell metacharacters."""
    return subprocess.run(
        ["docker", *args],
        check=check,
        capture_output=capture,
        input=input_bytes,
        timeout=timeout,
    )


@dataclass
class CircuitResult:
    """The verifiable outcome of one e2e fixture run (all offline-checkable)."""

    run_id: str
    seed: int
    engine: str
    delivered: bool
    payload_sha256: str
    received_sha256: str
    hop_containers: List[str]
    pcaps: Dict[int, Path] = field(default_factory=dict)
    pcap_sha256: Dict[int, str] = field(default_factory=dict)
    events_sha256: Optional[str] = None


def _seed_payload(seed: int, size: int = 4096) -> bytes:
    """A self-generated, seed-deterministic payload (no real data). Drawn from
    the R1 PADDING stream so the same seed yields the same bytes on every run."""
    stream = SorRng(seed).stream(Domain.PADDING)
    return bytes(stream.next_below(256) for _ in range(size))


def run_circuit_fixture(
    seed: int,
    *,
    engine: str = "docker",
    hops: int = 3,
    out_root: Optional[Path] = None,
    payload_size: int = 4096,
    keep: bool = False,
) -> CircuitResult:
    """Drive instrument-validation gate item 1: an ``hops``-hop nested-SSH circuit
    of isolated containers delivers a seed-deterministic payload end-to-end, with
    a per-hop pcap captured + checksummed and R3 events emitted.

    Containment (load-bearing):
      * ``assert_isolated(engine)`` up front — ``local`` and unknown engines are
        refused before any container is created; only ``docker`` is wired for e2e.
      * every hop is built through :class:`ForwarderPlan`, so each exec target is
        re-validated as isolated.
      * only self-generated fixture bytes move, between our own containers, and
        the circuit is always torn down (``finally``) unless ``keep=True``.

    Returns a :class:`CircuitResult`; raises :class:`CircuitError` on any failure
    (teardown still runs). Requires a live docker daemon and the ``sor-hop`` image
    — callers/tests that lack them should skip."""
    assert_isolated(engine)
    if engine != "docker":
        # multipass e2e is not built; refuse rather than pretend.
        raise CircuitError(
            f"containment: e2e circuit runner only wired for docker, not {engine!r}"
        )
    if shutil.which("docker") is None:
        raise CircuitError("docker control plane not found on PATH")
    if hops < 3:
        raise CircuitError(f"gate item 1 requires >=3 hops, got {hops}")

    run_id = f"sorfix-{seed:016x}-{int(time.time())}"
    out_root = Path(out_root) if out_root else Path("output/sor-runs")
    run_dir = out_root / run_id
    pcap_dir = run_dir / "pcap"
    pcap_dir.mkdir(parents=True, exist_ok=True)

    net = f"sorfix-net-{run_id}"
    client = f"sorfix-client-{run_id}"
    hop_names = [f"sorfix-hop{i}-{run_id}" for i in range(hops)]
    hop_alias = [f"hop{i}" for i in range(hops)]

    payload = _seed_payload(seed, payload_size)
    payload_sha = hashlib.sha256(payload).hexdigest()

    log = EventLog(run_dir, run_id, seed)
    result = CircuitResult(
        run_id=run_id,
        seed=seed,
        engine=engine,
        delivered=False,
        payload_sha256=payload_sha,
        received_sha256="",
        hop_containers=list(hop_names),
    )

    created: List[str] = []
    net_created = False
    try:
        # 1) Isolated user-defined network so hops resolve each other by alias.
        _docker("network", "create", net)
        net_created = True

        # 2) Bring up client + hop containers (each hop is a ForwarderPlan-gated
        #    isolated target; building the plan re-asserts containment).
        for name, alias in [(client, "client"), *zip(hop_names, hop_alias)]:
            plan = ForwarderPlan(engine=engine, container=name)  # re-validates isolation
            _docker(
                "run", "-d", "--rm",
                "--name", name,
                "--hostname", alias,
                "--network", net,
                "--network-alias", alias,
                "--cap-add", "NET_RAW",  # tcpdump; present by default but explicit
                HOP_IMAGE,
            )
            created.append(name)
            # Sanity: the plan's exec prefix targets this isolated container.
            assert plan.exec_prefix()[:3] == ["docker", "exec", "-i"]

        # 3) Client keypair + accept-on-first-use ssh config (client only).
        _docker("exec", client, "sh", "-c",
                "ssh-keygen -t ed25519 -N '' -f /root/.ssh/id_ed25519 -q")
        _docker("exec", "-i", client, "sh", "-c",
                "cat > /root/.ssh/config && chmod 600 /root/.ssh/config",
                input_bytes=_CLIENT_SSH_CONFIG.encode())
        pub = _docker("exec", client, "cat", "/root/.ssh/id_ed25519.pub").stdout

        # 4) Authorize the client key on every hop.
        for name in hop_names:
            _docker("exec", "-i", name, "sh", "-c",
                    "cat >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys",
                    input_bytes=pub)

        log.emit("circuit_build", circuit_id=run_id, hop_index=hops)

        # 5) Start a per-hop pcap (adjacent-hop SSH ciphertext only — the nested
        #    onion property). Detached so capture spans the transfer.
        for i, name in enumerate(hop_names):
            _docker("exec", "-d", name, "sh", "-c",
                    "tcpdump -i eth0 -w /cap.pcap 'tcp port 22' >/dev/null 2>&1")
            log.emit("hop_add", node_fp=hop_alias[i].encode().hex()[:8],
                     circuit_id=run_id, hop_index=i, bytes_=payload_size)
        time.sleep(1.0)  # let tcpdump bind before traffic

        # 6) Stage payload in the client, push it through the nested-SSH chain to
        #    the final hop, read it back. ProxyJump nests hop0->hop1->...->hopN-1.
        _docker("exec", "-i", client, "sh", "-c",
                "cat > /tmp/payload", input_bytes=payload)
        jumps = ",".join(f"root@{a}" for a in hop_alias[:-1])
        final = f"root@{hop_alias[-1]}"
        t0 = time.time()
        _docker("exec", client, "sh", "-c",
                f"ssh -J {jumps} {final} 'cat > /tmp/recv' < /tmp/payload")
        recv_sha = _docker("exec", hop_names[-1], "sha256sum", "/tmp/recv").stdout
        latency_ms = (time.time() - t0) * 1000.0
        received_sha = recv_sha.decode().split()[0]
        result.received_sha256 = received_sha
        result.delivered = received_sha == payload_sha
        log.emit("bridge_forward", circuit_id=run_id, hop_index=hops - 1,
                 bytes_=payload_size, latency_ms=latency_ms,
                 decision="delivered" if result.delivered else "corrupt")

        if not result.delivered:
            raise CircuitError(
                f"e2e delivery mismatch: sent {payload_sha[:12]} got {received_sha[:12]}"
            )

        # 7) Stop capture, copy each pcap out, checksum it (write-once artifact).
        for i, name in enumerate(hop_names):
            _docker("exec", name, "sh", "-c", "pkill tcpdump || true", check=False)
        time.sleep(0.5)
        for i, name in enumerate(hop_names):
            dst = pcap_dir / f"hop{i}.pcap"
            _docker("cp", f"{name}:/cap.pcap", str(dst))
            result.pcaps[i] = dst
            result.pcap_sha256[i] = hashlib.sha256(dst.read_bytes()).hexdigest()

        result.events_sha256 = log.close()
        return result
    except subprocess.CalledProcessError as exc:  # noqa: PERF203
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        raise CircuitError(f"docker control-plane step failed: {exc} {stderr}") from exc
    finally:
        if not log._closed:
            log.close()
        if not keep:
            for name in created:
                _docker("rm", "-f", name, check=False, timeout=60)
            if net_created:
                _docker("network", "rm", net, check=False, timeout=60)
