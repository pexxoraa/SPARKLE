#!/bin/sh
set -eu

usage() {
    echo "usage: sudo $0 CLIENT_USER"
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
    echo "private local worker provisioning requires root" >&2
    exit 1
fi

client_user=$1
if [ "$client_user" = "root" ] || ! id "$client_user" >/dev/null 2>&1; then
    echo "CLIENT_USER must be an existing non-root account" >&2
    exit 1
fi
for command in openssl install getent awk sed mktemp stat wc; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "$command is required" >&2
        exit 1
    fi
done
if ! id sparkle-worker >/dev/null 2>&1; then
    echo "sparkle-worker account is not provisioned" >&2
    exit 1
fi

worker_conf=/etc/sparkle/worker.conf
worker_signing_key=/etc/sparkle/worker-signing-key
for required in "$worker_conf" "$worker_signing_key"; do
    if [ ! -f "$required" ] || [ -L "$required" ]; then
        echo "required worker configuration is missing or unsafe: $required" >&2
        exit 1
    fi
done
key_bytes=$(wc -c < "$worker_signing_key")
if [ "$key_bytes" -lt 32 ] || [ "$key_bytes" -gt 4096 ]; then
    echo "worker signing key length is outside the supported bound" >&2
    exit 1
fi

client_home=$(getent passwd "$client_user" | awk -F: 'NR==1 {print $6}')
client_group=$(id -gn "$client_user")
if [ -z "$client_home" ] || [ ! -d "$client_home" ] || [ -L "$client_home" ]; then
    echo "CLIENT_USER home directory is unavailable or unsafe" >&2
    exit 1
fi
if [ -e "$client_home/.config" ] && [ -L "$client_home/.config" ]; then
    echo "CLIENT_USER .config must not be a symlink" >&2
    exit 1
fi

worker_id=$(sed -n 's/^SPARKLE_WORKER_ID=//p' "$worker_conf" | tail -n 1)
if ! printf '%s' "$worker_id" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9_.-]{1,127}$'; then
    echo "SPARKLE_WORKER_ID is missing or invalid" >&2
    exit 1
fi

tls_dir=/var/lib/sparkle-worker/tls
client_dir=$client_home/.config/sparkle
server_cert=$tls_dir/server.crt
server_key=$tls_dir/server.key
client_ca=$client_dir/worker-ca.crt
client_key=$client_dir/worker-signing-key
client_env=$client_dir/worker-client.env

install -d -o sparkle-worker -g sparkle-worker -m 0700 "$tls_dir"
install -d -o "$client_user" -g "$client_group" -m 0700 "$client_dir"

if [ -e "$server_cert" ] || [ -e "$server_key" ]; then
    if [ ! -f "$server_cert" ] || [ -L "$server_cert" ] || [ ! -f "$server_key" ] || [ -L "$server_key" ]; then
        echo "existing worker TLS material is incomplete or unsafe" >&2
        exit 1
    fi
    echo "Reusing existing private localhost TLS identity."
else
    temporary=$(mktemp -d)
    trap 'rm -rf "$temporary"' EXIT HUP INT TERM
    openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
        -subj "/CN=localhost/OU=SPARKLE private local" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
        -keyout "$temporary/server.key" -out "$temporary/server.crt" \
        >/dev/null 2>&1
    install -o sparkle-worker -g sparkle-worker -m 0400 "$temporary/server.key" "$server_key"
    install -o sparkle-worker -g sparkle-worker -m 0400 "$temporary/server.crt" "$server_cert"
    rm -rf "$temporary"
    trap - EXIT HUP INT TERM
    echo "Created a localhost-only TLS identity for the hardened worker."
fi

install -o "$client_user" -g "$client_group" -m 0600 "$server_cert" "$client_ca"
install -o "$client_user" -g "$client_group" -m 0600 "$worker_signing_key" "$client_key"

conf_tmp=$(mktemp)
trap 'rm -f "$conf_tmp"' EXIT HUP INT TERM
awk '!/^SPARKLE_WORKER_TLS_CERT_FILE=/ && !/^SPARKLE_WORKER_TLS_KEY_FILE=/ && !/^SPARKLE_WORKER_TRUSTED_TLS_TERMINATION=/' \
    "$worker_conf" > "$conf_tmp"
printf '\nSPARKLE_WORKER_TLS_CERT_FILE=%s\n' "$server_cert" >> "$conf_tmp"
printf 'SPARKLE_WORKER_TLS_KEY_FILE=%s\n' "$server_key" >> "$conf_tmp"
printf 'SPARKLE_WORKER_TRUSTED_TLS_TERMINATION=false\n' >> "$conf_tmp"
install -o root -g root -m 0600 "$conf_tmp" "$worker_conf"
rm -f "$conf_tmp"
trap - EXIT HUP INT TERM

env_tmp=$(mktemp)
trap 'rm -f "$env_tmp"' EXIT HUP INT TERM
cat > "$env_tmp" <<ENV
SPARKLE_EXTERNAL_WORKER_ENABLED=true
SPARKLE_EXTERNAL_WORKER_URL=https://localhost:8770/v1/jobs
SPARKLE_EXTERNAL_WORKER_ID=$worker_id
SSL_CERT_FILE=$client_ca
SPARKLE_EXTERNAL_WORKER_SIGNING_KEY_FILE=$client_key
ENV
install -o "$client_user" -g "$client_group" -m 0600 "$env_tmp" "$client_env"
rm -f "$env_tmp"
trap - EXIT HUP INT TERM

echo "Private local worker client material is provisioned without exposing credential contents."
echo "Restart sparkle-worker.service, then verify with:"
echo "curl --cacert $client_ca --fail --silent --show-error https://localhost:8770/health"
echo "Run SPARKLE through worker_environment/run-private-local-sparkle.sh to use the private worker."
