# SPARKLE external worker deployment

This directory packages the independent `SPARKLE-WORKER/1` fixed-unittest
service. The worker accepts no command, executable, argument, dependency, or
environment field. Its default Bubblewrap executor performs an isolation
preflight and refuses jobs unless filesystem and network namespaces work.

## Container deployment

Requirements: Docker Engine with Compose, a Linux host that permits
unprivileged user namespaces, a DNS name pointing to the host, and TCP/UDP 443.
Do not use `--privileged` or publish worker port 8770.

1. Create `worker_environment/secrets/worker-signing-key` with 48 or more
   cryptographically random bytes. For local Compose file secrets, make its
   numeric owner `10001:10001` and mode `0400` so the unprivileged container can
   read it without making it group/world-readable. This directory is ignored
   by Git. Use the deployment secret manager instead when it can set the target
   UID and mode itself.
2. Copy `worker.env.example` to the Git-ignored `.env.worker`, set the DNS name,
   and run from `worker_environment/`:

   ```bash
   cp worker.env.example .env.worker
   docker compose --env-file .env.worker build --pull
   docker compose --env-file .env.worker up -d
   docker compose --env-file .env.worker exec worker python3 -m sparkle.worker_service --check
   ```

3. Continue only if `ready` and both isolation fields are `true`. A check exit
   code of 2 is a safe refusal: the host/container runtime did not permit the
   required namespaces.
4. Configure SPARKLE with the HTTPS `/v1/jobs` URL and the same signing key,
   then run one explicitly approved external workspace test.

The Compose policy runs as UID 10001, drops all Linux capabilities, enables
`no-new-privileges`, uses a read-only image, gives only `/tmp` and the replay
database writable storage, keeps port 8770 on an internal network, and
terminates public TLS at Caddy. The nested Bubblewrap preflight is still
mandatory; container boundaries alone are not accepted as evidence.

## systemd deployment

Install SPARKLE in `/opt/sparkle/.venv`, create an unprivileged `sparkle-worker`
account and mode-0700 `/var/lib/sparkle-worker`, then install the unit. Put the
key at `/etc/sparkle/worker-signing-key` with root ownership and mode `0600`.
Configure loopback binding in `/etc/sparkle/worker.conf` and place a TLS reverse
proxy in front, or configure direct certificate/key files. Run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sparkle-worker
sudo -u sparkle-worker /opt/sparkle/.venv/bin/sparkle-worker --check
```

The systemd unit deliberately does not restrict namespace syscalls because the
nested sandbox requires them. It compensates with an unprivileged account,
read-only host paths, no capabilities, private devices/tmp, and a narrow
address-family set. The worker itself unshares network/filesystem namespaces
for each job and fails closed when that operation is unavailable.

## Development-only protocol smoke test

`make worker-dev` opts into the plain process executor. It is useful only on
loopback for protocol tests. Its status and every response explicitly report
filesystem/network isolation as false. Never expose it to untrusted source or
use it as a production worker.
