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
4. Configure SPARKLE with the HTTPS `/v1/jobs` URL, exact public worker ID, and
   the same signing key, then run one explicitly approved external workspace
   test. The client rejects a signed result from any other worker ID.

The Compose policy runs as UID 10001, drops all Linux capabilities, enables
`no-new-privileges`, uses a read-only image, gives only `/tmp` and the replay
database writable storage, keeps port 8770 on an internal network, and
terminates public TLS at Caddy. The nested Bubblewrap preflight is still
mandatory; container boundaries alone are not accepted as evidence.

## systemd deployment

Install SPARKLE in `/opt/sparkle/.venv`, create an unprivileged `sparkle-worker`
account and mode-0700 `/var/lib/sparkle-worker`, then install the unit. Put the
key at `/etc/sparkle/worker-signing-key` as a root-owned, root-group regular
non-symlink file with mode `0600` and 32–4096 bytes. `LoadCredential=` projects
it into the service namespace as root-owned mode `0440`; SPARKLE accepts that
mode only for the exact file beneath systemd's `CREDENTIALS_DIRECTORY`.
Arbitrary group-readable key files remain rejected. Configure loopback binding
in `/etc/sparkle/worker.conf` and place a TLS reverse proxy in front, or
configure direct certificate/key files. Run:

```bash
python3 -m build --wheel
sudo worker_environment/install-systemd-worker.sh "$PWD/dist/<wheel-name>.whl"
sudo install -o root -g root -m 0600 \
  worker_environment/worker.conf.example /etc/sparkle/worker.conf
sudo systemctl daemon-reload
sudo -u sparkle-worker /opt/sparkle/.venv/bin/sparkle-worker --check
sudo systemctl enable --now sparkle-worker
```

The installer accepts only an absolute regular non-symlink wheel, installs
without dependencies, creates the dedicated account and directories, installs
the hardened unit and a non-secret configuration example, and deliberately
does not create a signing key or start the service. Inject the key separately
before the preflight and service start.

The systemd unit deliberately does not restrict namespace syscalls because the
nested sandbox requires them. It also sets `ProtectKernelTunables=no`
explicitly: `ProtectKernelTunables=yes` changes the unit's kernel API filesystem
view, implies `MountAPIVFS=yes`, and on the supported Ubuntu host prevents
Bubblewrap from mounting the private `/proc` required inside its per-job user
and mount namespaces. This is a narrow compatibility exception, not permission
to change host tunables. The worker remains unprivileged with empty capability
and ambient-capability sets plus `NoNewPrivileges=yes`; it therefore has no
host capability with which to modify protected kernel settings. The unit keeps
`ProtectKernelModules=yes`, `ProtectKernelLogs=yes`, `ProtectSystem=strict`,
`ProtectHome=yes`, private devices/tmp, and the narrow address-family set.
Bubblewrap still unshares all namespaces, creates its private `/proc`, clears
the environment, mounts the artifact read-only, and must pass all seven
canaries before any job runs.

The systemd/Bubblewrap compatibility result is a host acceptance test, not a
unit-test claim. After installing a new wheel and unit, start—but do not
enable—the exact hardened service and invoke its health check, which runs the
real Bubblewrap preflight:

```bash
sudo systemctl stop sparkle-worker
sudo systemctl daemon-reload
sudo systemctl start sparkle-worker
curl --fail --silent --show-error http://127.0.0.1:8770/health
sudo systemctl status sparkle-worker --no-pager
sudo journalctl -u sparkle-worker -n 80 --no-pager
sudo systemctl stop sparkle-worker
```

Require exit code 0, `ready: true`, profile
`SPARKLE-WORKER-BUBBLEWRAP/1`, and all seven canaries `true`. Any absent or
false value is a hard stop. Do not enable or start the long-running service on
failure.

## Development-only protocol smoke test

`make worker-dev` opts into the plain process executor. It is useful only on
loopback for protocol tests. Its status and every response explicitly report
filesystem/network isolation as false. Never expose it to untrusted source or
use it as a production worker.

Run the credential-free host diagnostic first:

```bash
make worker-diagnose
```

It reports each user, mount, and network namespace probe with its command,
exit code, and bounded output; tests `no_new_privs`; and runs the real
Bubblewrap preflight. `AVAILABLE`, `UNAVAILABLE`, and `NOT_VERIFIED` are
distinct. The diagnostic always leaves `level_3_verified` false because host
capability detection is not the full Level 3 acceptance workflow.

For a separate local TLS/HMAC process worker, create development-only material
in the ignored secrets directory:

```bash
worker_environment/bootstrap-local-worker.sh
set -a
. worker_environment/secrets/local-development/worker.env
set +a
sparkle-worker
```

The bootstrap refuses overwrite, generates a mode-0600 HMAC key file and a
seven-day self-signed `localhost` certificate, and externalizes every path in
`worker.env`. Trust `server.crt` explicitly in the local client. Never reuse
these credentials or the process executor outside local development. The test
suite proves valid certificate/hostname verification and rejection of an
untrusted certificate and wrong hostname.

## Level 3 acceptance procedure

1. Record the VM distribution/kernel and successful user, mount, network, and
   PID namespace probes. Record commands, exit codes, and output without keys.
2. Run `sparkle-worker --check`. Require exit 0, the
   `SPARKLE-WORKER-BUBBLEWRAP/1` profile, and all seven named canaries `true`.
3. In the protected GitHub environment `sparkle-level3-worker`, configure
   `SPARKLE_EXTERNAL_WORKER_URL` and `SPARKLE_EXTERNAL_WORKER_ID` as variables
   and `SPARKLE_WORKER_SIGNING_KEY` as a secret.
4. Manually run `SPARKLE Level 3 Worker Acceptance`. Require TLS validation,
   response authentication, the pinned worker identity, all-true signed canary
   evidence, and a result digest. This probe deliberately does not complete
   Level 3 by itself.
5. From SPARKLE, authorize and execute one real immutable controlled-build
   artifact. Require equal authorized/executed artifact digests, verified
   lifecycle/result, cleanup, and `isolation_verified: true`.
6. Preserve the worker check, workflow run/job, controlled execution ID, worker
   ID, artifact digest, result digest, timestamps, and negative-test outcomes.
   Preserve no source, output containing secrets, HMAC key, TLS private key, or
   SSH private key.

Any false/absent canary, TLS error, wrong worker identity, invalid HMAC,
artifact mismatch, ambiguous evidence, or cleanup failure blocks Level 3.
