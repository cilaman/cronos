# Egress Allowlist for Cronos Containers

This document covers R8: container egress must be restricted to an allowlist of
known-good hosts. Docker Compose alone cannot express a host-level default-deny
egress policy; enforcement requires one of the two mechanisms below plus a manual
verification run by the operator on the deployment host.

## Required destinations

| Destination | Purpose |
|-------------|---------|
| `api.anthropic.com` (443) | Claude API — agent runs |
| `statsig.anthropic.com` (443) | Claude CLI feature flags |
| `sentry.io` (443) | Claude CLI error reporting |
| `github.com` (443) | Git clone / push for repo-linked spaces |
| `objects.githubusercontent.com` (443) | GitHub raw object downloads |
| Package registries (PyPI `pypi.org`, npm `registry.npmjs.org`) | Only needed at build time, not runtime |
| Internal `backend:8000` ↔ `caddy:80` | Already isolated to the compose network |

## Mechanism A — Host iptables OUTPUT rules (recommended for VPS deployments)

This approach adds OUTPUT chain rules scoped to the Docker bridge subnet so
only containers are restricted; host traffic is unaffected.

```bash
# Identify the Docker bridge subnet for the Cronos compose project.
BRIDGE=$(docker network inspect cronos-development_default \
    --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}')
# Example: 172.18.0.0/16

# Allow established/related traffic first (stateful).
iptables -I FORWARD 1 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow outbound DNS (port 53 UDP/TCP) from the bridge.
iptables -I FORWARD 2 -s "$BRIDGE" -p udp --dport 53 -j ACCEPT
iptables -I FORWARD 3 -s "$BRIDGE" -p tcp --dport 53 -j ACCEPT

# Allow HTTPS to Anthropic endpoints.
iptables -I FORWARD 4 -s "$BRIDGE" -p tcp --dport 443 \
    -d api.anthropic.com -j ACCEPT
iptables -I FORWARD 5 -s "$BRIDGE" -p tcp --dport 443 \
    -d statsig.anthropic.com -j ACCEPT
iptables -I FORWARD 6 -s "$BRIDGE" -p tcp --dport 443 \
    -d sentry.io -j ACCEPT

# Allow HTTPS to GitHub.
iptables -I FORWARD 7 -s "$BRIDGE" -p tcp --dport 443 \
    -d github.com -j ACCEPT
iptables -I FORWARD 8 -s "$BRIDGE" -p tcp --dport 443 \
    -d objects.githubusercontent.com -j ACCEPT

# Default-deny all other FORWARD traffic from containers.
iptables -A FORWARD -s "$BRIDGE" -j DROP
```

Persist with `iptables-save > /etc/iptables/rules.v4` (requires `iptables-persistent`).

**Note on DNS:** The rules above allow outbound DNS. If you prefer to pin DNS to a
specific resolver (e.g. `1.1.1.1`) rather than any resolver, replace the broad port-53
rule with `--dport 53 -d 1.1.1.1 -j ACCEPT`.

## Mechanism B — Forward-proxy sidecar (alternative)

Add a lightweight HTTP/HTTPS proxy (e.g. `squid` or `tinyproxy`) as a compose
service. Inject `HTTP_PROXY` / `HTTPS_PROXY` env vars into the backend service
and configure the proxy's ACL to allow only the destinations above.

```yaml
# In docker-compose.yml (fragment):
services:
  proxy:
    image: tinyproxy/tinyproxy:latest
    # Configure via /etc/tinyproxy/tinyproxy.conf with Allow directives

  backend:
    environment:
      HTTP_PROXY: "http://proxy:8888"
      HTTPS_PROXY: "http://proxy:8888"
      NO_PROXY: "caddy,localhost"
```

This is more portable across cloud environments but adds a service to the stack.

## Manual verification checklist (R8)

Run these commands **inside the running backend container** after applying either
mechanism. Record the output next to each step.

```bash
# Enter the backend container
docker exec -it cronos-development-backend-1 sh

# 1. Confirm running as non-root (R1)
id
# Expected: uid=1001(cronos) gid=1001(cronos)

# 2. Deliberate exfiltration to an unlisted host MUST FAIL (R8 key assertion)
curl -v --max-time 10 http://example.com
# Expected: connection timed out or connection refused (NOT 200 OK)

# 3. Anthropic API must be reachable
curl -sv --max-time 10 https://api.anthropic.com/v1/models \
    -H "x-api-key: invalid" 2>&1 | grep -E "< HTTP|Connected to"
# Expected: HTTP/2 401 (unauthorised, but connectivity confirmed)

# 4. GitHub must be reachable
git ls-remote https://github.com/octocat/Hello-World HEAD
# Expected: a commit SHA printed to stdout (no auth error, no timeout)

# 5. Claude CLI is executable as non-root (R2)
claude --version
# Expected: version string printed, no permission error
```

Record results in `.cronos/qa/g03-egress-verification.md` after the smoke run.

## Ops notes: UID 1001 and host bind-mounts

The backend container now runs as UID 1001 (`cronos`). The `docker-entrypoint.sh`
script idempotently re-chowns the `./data` bind-mount on every startup
(`chown -R --from=0 cronos:cronos /data`) so root-owned data from previous
deployments is automatically corrected.

**Consequences for host tooling:**
- The nightly backup (`cronos-backup.service`) runs as root via systemd and reads
  `/opt/cronos/data` — unaffected, root can always read UID 1001 files.
- Developer machines that access `./data` directly (e.g. to inspect SQLite with
  `sqlite3 ./data/db.sqlite3`) will succeed if the host user is root; non-root
  host users may need `sudo` or to be in the `cronos` group if it exists on the
  host.
- The `upgrade.sh` script runs as root (called by the upgrade webhook service)
  and has no permission issues.

If you need host users to read/write `./data` directly without sudo, add them to
a group that matches GID 1001 on the host, or configure a shared supplementary
group in the systemd unit.
