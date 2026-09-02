#!/bin/sh
set -eu

usage() {
    echo "usage: sudo $0 /absolute/path/to/sparkle-wheel.whl"
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi
if [ "$#" -ne 1 ]; then
    usage >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
    echo "systemd worker installation requires root" >&2
    exit 1
fi

wheel=$1
case "$wheel" in
    /*) ;;
    *) echo "wheel path must be absolute" >&2; exit 1 ;;
esac
if [ ! -f "$wheel" ] || [ -L "$wheel" ]; then
    echo "wheel must be a regular non-symlink file" >&2
    exit 1
fi

for command in python3 systemctl bwrap; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "$command is required" >&2
        exit 1
    fi
done

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

if ! id sparkle-worker >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/sparkle-worker \
        --shell /usr/sbin/nologin sparkle-worker
fi

install -d -m 0755 /opt/sparkle
install -d -o sparkle-worker -g sparkle-worker -m 0700 /var/lib/sparkle-worker
install -d -o root -g root -m 0700 /etc/sparkle

if [ ! -x /opt/sparkle/.venv/bin/python ]; then
    python3 -m venv /opt/sparkle/.venv
fi
/opt/sparkle/.venv/bin/python -m pip install --no-deps --upgrade "$wheel"

install -o root -g root -m 0644 \
    "$script_dir/sparkle-worker.service" /etc/systemd/system/sparkle-worker.service
install -o root -g root -m 0600 \
    "$script_dir/worker.conf.example" /etc/sparkle/worker.conf.example
systemctl daemon-reload

echo "Worker software installed but not started."
echo "Create /etc/sparkle/worker.conf and inject /etc/sparkle/worker-signing-key."
echo "Then run: sudo -u sparkle-worker /opt/sparkle/.venv/bin/sparkle-worker --check"
echo "Enable the service only after the isolation preflight passes."
