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
sudo usermod -aG docker $USER
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

**On the VPS**, store it in a chmod-600 env file. Never write the token to
`.bashrc`, shell history, or a committed file:

```bash
mkdir -p ~/.config/claude
umask 077
cat > ~/.config/claude/env <<'EOF'
CLAUDE_CODE_OAUTH_TOKEN=paste-token-here
EOF
chmod 600 ~/.config/claude/env
ls -l ~/.config/claude/env   # should show -rw-------
```

The compose prod overlay points the backend container at this file via
`env_file: ${HOME}/.config/claude/env`, so it's loaded directly into the
container without ever appearing in `docker compose config` dumps or shell
history.

---

## 5. Clone and configure Cronos

```bash
sudo mkdir -p /opt/cronos
sudo chown $USER:$USER /opt/cronos
git clone <your-repo-url> /opt/cronos
cd /opt/cronos

cp .env.example .env
# Edit .env and set DOMAIN, BASIC_AUTH_USER, BASIC_AUTH_HASH.
# Generate the bcrypt hash:
docker run --rm caddy caddy hash-password --plaintext 'your-password-here'
# Paste the output into BASIC_AUTH_HASH=...
nano .env
```

Leave `CLAUDE_CODE_OAUTH_TOKEN` out of `.env` — it lives in
`~/.config/claude/env` and is loaded by the prod overlay. Keeping the two
files separate means a leaked `.env` (basic-auth creds + domain) doesn't
leak the OAuth token.

---

## 6. First run

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
```

The systemd unit picks up the same compose files, so a subsequent
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
- [ ] `systemctl status cronos.service` shows `active (exited)` and the
      compose services are up
- [ ] `systemctl list-timers cronos-backup.timer` shows a future fire time
- [ ] `sudo systemctl start cronos-backup.service` produces a tarball under
      `/var/backups/cronos/`
- [ ] After `sudo reboot`, the stack and backup timer come back up
      automatically
- [ ] Mobile, tablet, and laptop browsers all render the board correctly
