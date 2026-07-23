# R4 fixture — one isolated SOR relay hop.
#
# A minimal Alpine node running sshd, used ONLY as a lab relay for
# self-generated fixture traffic inside the isolated engine (docker). It never
# runs on the host (the forwarder guard refuses engine == local) and is torn
# down after each run. openssh-client + tcpdump are present so the node can be a
# nested-SSH jump host and so per-hop pcaps can be captured for the linkability
# measurement (all traffic is SSH-encrypted self-traffic).
FROM alpine:latest

# Alpine's stock sshd_config ships `AllowTcpForwarding no` (and sshd honours the
# FIRST occurrence of a keyword), so we strip any pre-set copies of the keywords
# we care about before appending our nested-SSH relay policy — otherwise the
# jump-host onward channel is refused ("stdio forwarding failed").
RUN apk add --no-cache openssh openssh-client tcpdump \
 && ssh-keygen -A \
 && mkdir -p /root/.ssh && chmod 700 /root/.ssh \
 && sed -i -E '/^[#[:space:]]*(AllowTcpForwarding|PermitRootLogin|PubkeyAuthentication|PasswordAuthentication|UseDNS)\b/d' /etc/ssh/sshd_config \
 && printf '\n# --- SOR relay policy ---\nPermitRootLogin prohibit-password\nPubkeyAuthentication yes\nPasswordAuthentication no\nAllowTcpForwarding yes\nUseDNS no\n' \
      >> /etc/ssh/sshd_config

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D", "-e"]
