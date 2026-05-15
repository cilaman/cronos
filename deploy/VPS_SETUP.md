# VPS setup

End-to-end checklist for running Cronos on a personal Linux VPS, authenticated
against a Claude Pro/Max subscription (no API key, no API billing). Adapt to
your distro; commands below assume Ubuntu 24.04.

> **Scope:** strictly personal automation. Per Anthropic ToS, subscription OAuth
> tokens are not for third-party products or shared accounts.

---

## 1. Prerequisites

On your **local machine** (where you'll generate the OAuth token):

- Node.js 22+ (`node -v`)
- `claude` CLI: `npm install -g @anthropic-ai/claude-code`

On the **VPS**:

- Ubuntu 24.04 (or any current LTS)
- A DNS A/AAAA record pointing `cronos.example.com` at the VPS public IP
- SSH access as a sudo user

---

## 2. Harden the VPS

```bash
# 2.1 — Create a non-root user (skip if you already have one)
sudo adduser cronos
sudo usermod -aG sudo cronos

# 2.2 — Copy your SSH key for the new user
sudo rsync -a --chown=cronos:cronos ~/.ssh/authorized_keys /home/cronos/.ssh/

# 2.3 — Disable root + password SSH
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# 2.4 — Firewall: SSH + HTTP + HTTPS only
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# 2.5 — Unattended security upgrades
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

Log out of root and back in as `cronos` for everything below.

---

## 3. Install Docker

```bash
# Official Docker convenience script
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker cronos    # NOT $USER — the systemd unit runs as cronos
# Log out and back in for the group change to take effect
```

Verify: `docker run --rm hello-world`.

---

## 4. Provision the Claude OAuth token

**On your local Mac** (NOT on the VPS):

```bash
claude setup-token
```

This will open a browser, log you in, and print a long-lived OAuth token. Copy
it to your clipboard — it will only be shown once.

**On the VPS, as the `cronos` user** (not root), store it in a chmod-600
env file. Never write the token to `.bashrc`, shell history, or a committed
file:

```bash
mkdir -p ~/.config/claude
umask 077
cat > ~/.config/claude/env <<'EOF'
CLAUDE_CODE_OAUTH_TOKEN=paste-token-here
EOF
chmod 600 ~/.config/claude/env
ls -l ~/.config/claude/env   # should show -rw------- cronos cronos
```

The compose prod overlay points the backend container at this file via
`env_file: ${HOME}/.config/claude/env`, so it's loaded directly into the
container without ever appearing in `docker compose config` dumps or shell
history.

> ⚠️ **Why the `cronos` user matters here.** Docker Compose expands
> `${HOME}` *at invoke time*, based on the user running `docker compose`.
> The systemd unit (§7) runs as `cronos`, so `${HOME}=/home/cronos` and the
> token is found. If you ever start the stack manually as `root` (e.g.
> `sudo docker compose up`, or a root shell in `/opt/cronos`),
> `${HOME}=/root`, Compose looks in `/root/.config/claude/env`, doesn't
> find it, and **silently skips loading** — `env_file` is marked
> `required: false` so dev machines without a token can still boot. The
> backend then runs without `CLAUDE_CODE_OAUTH_TOKEN`, the `claude` CLI
> can't authenticate, and the UI gets stuck on `LIVE: connecting` for
> every iteration. **Always (re)start via `sudo systemctl restart
> cronos.service`** — that's the only path that resolves `${HOME}`
> correctly.

---

## 5. Clone and configure Cronos

> Run this section as the `cronos` user, not root.

### 5.1 — Create a read-only GitHub deploy key

The VPS needs SSH access to clone (and later `git pull`) a private repo. A
deploy key is scoped to one repo and has no account-wide access, so it is
safe to leave on the VPS long-term:

```bash
ssh-keygen -t ed25519 -C "cronos-vps-deploy-key" -f ~/.ssh/github_cronos -N ""

cat >> ~/.ssh/config <<'EOF'

Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_cronos
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config ~/.ssh/github_cronos

cat ~/.ssh/github_cronos.pub
```

Copy the printed public key, then in GitHub:
**Repo → Settings → Deploy keys → Add deploy key.** Paste the key, give it a
title (e.g. `cronos VPS`), leave **Allow write access** *unchecked*, save.

Verify the handshake:

```bash
ssh -T git@github.com   # "Hi <owner>/<repo>! You've successfully authenticated..."
```

`IdentitiesOnly yes` is important — without it, OpenSSH offers every key in
`~/.ssh/` before the deploy key and GitHub closes the connection after too
many wrong attempts.

### 5.2 — Clone and configure env

```bash
sudo mkdir -p /opt/cronos
sudo chown $USER:$USER /opt/cronos
git clone git@github.com:<owner>/<repo>.git /opt/cronos
cd /opt/cronos

cp .env.example .env
# Edit .env and set DOMAIN, BASIC_AUTH_USER, BASIC_AUTH_HASH.
# Generate the bcrypt hash:
docker run --rm caddy caddy hash-password --plaintext 'your-password-here'
# Paste the output into BASIC_AUTH_HASH=, BUT escape every `$` as `$$`:
#   real hash:    $2a$14$TxGxYeXXN0i...
#   put in .env:  $$2a$$14$$TxGxYeXXN0i...
# Otherwise docker compose treats `$2a`, `$14`, etc. as variable references
# and silently expands them to empty strings.
nano .env
```

Sanity-check the parsed value before starting any services:

```bash
docker compose --env-file .env \
  -f docker-compose.yml -f docker-compose.prod.yml config \
  | grep BASIC_AUTH_HASH
# Should print the full $2a$14$... hash, no "variable not set" warnings.
```

Leave `CLAUDE_CODE_OAUTH_TOKEN` out of `.env` — it lives in
`~/.config/claude/env` and is loaded by the prod overlay. Keeping the two
files separate means a leaked `.env` (basic-auth creds + domain) doesn't
leak the OAuth token.

---

## 6. First run

> Run as the `cronos` user — not `sudo`, not a root shell. See the
> `${HOME}` note in §4 for why this matters.

```bash
cd /opt/cronos
docker compose \
  --env-file .env \
  -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --build
```

Watch the logs until Caddy reports a successful certificate:

```bash
docker compose logs -f caddy
```

---

## 7. systemd units (autostart on boot, nightly backup)

The repo ships three units in `deploy/`:

- `cronos.service` — runs `docker compose up -d` on boot
- `cronos-backup.service` — one-shot wrapper around `deploy/backup.sh`
- `cronos-backup.timer` — fires the backup daily at ~03:17 UTC

Install them as the cronos user:

```bash
sudo install -m 644 /opt/cronos/deploy/cronos.service          /etc/systemd/system/
sudo install -m 644 /opt/cronos/deploy/cronos-backup.service   /etc/systemd/system/
sudo install -m 644 /opt/cronos/deploy/cronos-backup.timer     /etc/systemd/system/

sudo install -d -o cronos -g cronos /var/backups/cronos

sudo systemctl daemon-reload
sudo systemctl enable --now cronos.service
sudo systemctl enable --now cronos-backup.timer

systemctl status cronos.service
systemctl list-timers cronos-backup.timer
```

To trigger a backup immediately (good smoke test):

```bash
sudo systemctl start cronos-backup.service
ls -lh /var/backups/cronos/
```

`backup.sh` keeps the last 14 daily tarballs by default; override with
`RETENTION=` or `BACKUP_DIR=` env vars if you want different behaviour.

---

## 8. Log rotation

Container stdout/stderr is captured by Docker's `json-file` log driver,
capped at `max-size=10m` × `max-file=5` per service in
`docker-compose.prod.yml`. No host-side `logrotate` config is needed for
container logs — Docker handles the rotation itself.

To inspect current sizes:

```bash
sudo du -sh /var/lib/docker/containers/*/*-json.log
```

If you want logs shipped off the box (Loki, Papertrail, etc.) swap the
driver in the prod overlay; the rest of the stack doesn't care.

---

## 9. Token hygiene & rotation

- `~/.config/claude/env` must stay `chmod 600`, owned by `cronos`. It is
  never written to `.bashrc`, shell history, or any committed file.
- The token is a long-lived OAuth credential against your personal Pro/Max
  subscription. Treat it like a password.
- **Rotate** by running `claude setup-token` again on your local Mac,
  replacing the file on the VPS, then restarting the backend container:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    restart backend
  ```
- **Revoke** the old token from your Claude account settings if you suspect
  compromise, *before* deploying the new one.

---

## 10. Upgrades

```bash
cd /opt/cronos
git pull
docker compose \
  --env-file .env \
  -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --build
  sudo systemctl restart cronos.service
```

`git pull` authenticates unattended via the deploy key set up in §5.1 — no
prompts. The systemd unit picks up the same compose files, so a subsequent
`systemctl restart cronos.service` will start the freshly-built images.

---

## 11. Verification checklist

- [ ] `https://<domain>` loads the Cronos page over TLS (valid cert)
- [ ] Wrong basic-auth credentials are rejected
- [ ] `curl -u user:pass https://<domain>/api/health` returns
      `{"ok": true, ..., "claude_on_path": true, "worker_running": true}`
- [ ] `docker inspect --format '{{.State.Health.Status}}' $(docker compose ps -q backend)`
      reports `healthy`
- [ ] `ls -l /home/cronos/.config/claude/env` shows `-rw-------`
- [ ] `docker compose exec backend printenv CLAUDE_CODE_OAUTH_TOKEN | head -c 20`
      prints the first chars of the token (not empty) — confirms the
      `env_file` was actually loaded into the container. If empty, the
      stack was started by the wrong user; see §4.
- [ ] `systemctl status cronos.service` shows `active (exited)` and the
      compose services are up
- [ ] `systemctl list-timers cronos-backup.timer` shows a future fire time
- [ ] `sudo systemctl start cronos-backup.service` produces a tarball under
      `/var/backups/cronos/`
- [ ] After `sudo reboot`, the stack and backup timer come back up
      automatically
- [ ] Mobile, tablet, and laptop browsers all render the board correctly

---

## 12. Browser access & auth choice

### Chrome and HTTP basic-auth — known UX quirk

Chrome 130+ has been suppressing the basic-auth login dialog in cases where
it has previously seen a 401 for that hostname (or where an extension
intercepts the request). The symptom in DevTools is
`net::ERR_HTTP_RESPONSE_CODE_FAILURE 401` with no dialog ever appearing,
even though `WWW-Authenticate: Basic` is present in the response headers.

Workarounds, easiest first:

- **Open in Safari or Firefox** — they prompt reliably.
- **Pre-fill credentials via URL once**: `https://user:pass@<domain>/`. Chrome
  strips the userinfo from the address bar but uses it for the initial auth
  and caches it for the session.
- **Reset Chrome state for the host**: clear site data, delete the HSTS entry
  at `chrome://net-internals/#hsts`, then fully quit Chrome (Cmd-Q) and
  reopen. A fresh Chrome profile also works.

If you find this annoying enough to want to replace basic-auth entirely,
**Tailscale (below) is the simplest answer** for a single-user personal
install.

### Tailscale — recommended auth replacement for personal use

Putting the VPS on Tailscale and dropping basic-auth entirely gives you:

- No login dialog of any kind (Tailscale handles identity at the network
  layer)
- The Cronos UI becomes invisible to the public internet — a whole class of
  attacks just disappears
- Works identically on Mac, iOS, Android, with no `/etc/hosts` tricks
- Free for personal use (up to 100 devices, 3 users)

#### Setup

```bash
# 12.1 — On the VPS, install and authenticate Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up                    # opens an auth URL, log in
sudo tailscale ip -4                 # note the 100.x.x.x address
sudo tailscale status                # note the *.ts.net hostname
```

Install the Tailscale client on each device you'll use (Mac/iOS/Android from
[tailscale.com/download](https://tailscale.com/download) or the relevant app
store) and authenticate to the same tailnet.

#### Remove basic-auth and restrict 443 to the tailnet

```bash
# 12.2 — Drop basic_auth from the Caddyfile (it's no longer needed)
sed -i '/basic_auth \* {/,/^    }/d' /opt/cronos/Caddyfile

# 12.3 — Firewall: block public access to 443, allow only Tailnet (100.64/10).
# Port 80 stays open for Let's Encrypt HTTP-01 cert renewal.
sudo ufw allow from 100.64.0.0/10 to any port 443
sudo ufw delete allow 443/tcp           # remove the previous "open to world" rule
sudo ufw status numbered                # sanity-check the rules

# 12.4 — Apply
docker compose --env-file /opt/cronos/.env \
  -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --force-recreate caddy
```

#### Verify

- From a Tailnet device: `https://<domain>/` loads Cronos directly with no
  password prompt and a valid LE cert.
- From a non-Tailnet network (e.g. mobile data with Tailscale off): the same
  URL hangs / times out on 443 — exactly what you want.
- `http://<domain>/` still redirects to HTTPS and reaches Caddy on port 80,
  so LE renewals continue to work.

You can also drop the public DNS record entirely and use the Tailscale
MagicDNS hostname (e.g. `https://cronos-vps.<tailnet>.ts.net/`) with
`tailscale cert` for an auto-renewed cert — but keeping `cronos.ultc.at` +
LE works just as well and means you don't have to change the Caddyfile
hostname.

### `BASIC_AUTH_*` after switching to Tailscale

You can leave the `BASIC_AUTH_USER` / `BASIC_AUTH_HASH` values in `.env` —
they're simply unused once `basic_auth` is removed from the Caddyfile.
Or delete them; both work.
