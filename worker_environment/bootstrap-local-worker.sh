#!/bin/sh
set -eu

umask 077

if ! command -v openssl >/dev/null 2>&1; then
    echo "OpenSSL is required" >&2
    exit 1
fi

output_dir=${1:-worker_environment/secrets/local-development}
case "$output_dir" in
    ""|/|.|..) echo "Refusing unsafe output directory" >&2; exit 1 ;;
esac

if [ -e "$output_dir" ]; then
    echo "Refusing to overwrite existing local worker secrets" >&2
    exit 1
fi

mkdir -p "$output_dir/tls" "$output_dir/state"
chmod 700 "$output_dir" "$output_dir/tls" "$output_dir/state"

openssl rand 48 > "$output_dir/worker-signing-key"
chmod 600 "$output_dir/worker-signing-key"

openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 7 \
    -subj "/CN=localhost/OU=SPARKLE development only" \
    -addext "subjectAltName=DNS:localhost" \
    -keyout "$output_dir/tls/server.key" \
    -out "$output_dir/tls/server.crt" >/dev/null 2>&1
chmod 600 "$output_dir/tls/server.key"
chmod 644 "$output_dir/tls/server.crt"

absolute_dir=$(CDPATH= cd -- "$output_dir" && pwd -P)
cat > "$output_dir/worker.env" <<EOF
SPARKLE_WORKER_HOST=127.0.0.1
SPARKLE_WORKER_PORT=9443
SPARKLE_WORKER_ID=sparkle-local-development-worker
SPARKLE_WORKER_STATE_DIR=$absolute_dir/state
SPARKLE_WORKER_SIGNING_KEY_FILE=$absolute_dir/worker-signing-key
SPARKLE_WORKER_TLS_CERT_FILE=$absolute_dir/tls/server.crt
SPARKLE_WORKER_TLS_KEY_FILE=$absolute_dir/tls/server.key
SPARKLE_WORKER_EXECUTOR=process
SPARKLE_WORKER_ALLOW_UNSAFE_PROCESS_EXECUTOR=true
EOF
chmod 600 "$output_dir/worker.env"

echo "Created NON-ISOLATED development worker configuration in $output_dir"
echo "The certificate expires after 7 days and is valid only for localhost."
echo "Level 3 remains BLOCKED."
