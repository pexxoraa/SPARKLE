#!/bin/sh
set -eu

config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}/sparkle
env_file=$config_home/worker-client.env
if [ ! -f "$env_file" ] || [ -L "$env_file" ]; then
    echo "private local worker client configuration is not provisioned" >&2
    exit 1
fi
# Root-generated local configuration contains paths/identity only; no secret value.
# shellcheck disable=SC1090
. "$env_file"
export SPARKLE_EXTERNAL_WORKER_ENABLED SPARKLE_EXTERNAL_WORKER_URL
export SPARKLE_EXTERNAL_WORKER_ID SPARKLE_EXTERNAL_WORKER_SIGNING_KEY_FILE SSL_CERT_FILE

cli=${SPARKLE_PRIVATE_CLI:-sparkle}
exec "$cli" "$@"
