#!/bin/sh
# Linux container only. Run BEFORE the normal EAP process starts.
# Requires a writable, existing standalone configuration in JBOSS_HOME.
set -eu

: "${JBOSS_HOME:?Set JBOSS_HOME to the actual EAP installation directory}"
task_config=${EAP_SERVER_CONFIG:-standalone.xml}
task_server=${UNDERTOW_SERVER:-default-server}
task_listener=${UNDERTOW_HTTP_LISTENER:-default}

for task_value in "$task_config" "$task_server" "$task_listener"; do
    case "$task_value" in
        ''|*[!A-Za-z0-9_.-]*)
            printf '%s\n' 'Invalid configuration or resource name.' >&2
            exit 2
            ;;
    esac
done

task_cli="$JBOSS_HOME/bin/jboss-cli.sh"
task_config_path="$JBOSS_HOME/standalone/configuration/$task_config"
if [ ! -x "$task_cli" ]; then
    printf '%s\n' 'jboss-cli.sh is missing or not executable.' >&2
    exit 2
fi
if [ ! -f "$task_config_path" ] || [ ! -w "$task_config_path" ]; then
    printf '%s\n' 'Existing standalone configuration must be writable.' >&2
    exit 2
fi

task_tmp=$(mktemp "${TMPDIR:-/tmp}/eap-forwarding.XXXXXX")
trap 'rm -f "$task_tmp"' 0
trap 'exit 1' 1 2 15
cat > "$task_tmp" <<EOF
embed-server --std-out=echo --admin-only=true --timeout=60 --server-config=$task_config
if (result != true) of /subsystem=undertow/server=$task_server/http-listener=$task_listener:read-attribute(name=proxy-address-forwarding)
    /subsystem=undertow/server=$task_server/http-listener=$task_listener:write-attribute(name=proxy-address-forwarding,value=true)
end-if
/subsystem=undertow/server=$task_server/http-listener=$task_listener:read-attribute(name=proxy-address-forwarding)
stop-embedded-server
EOF
"$task_cli" --file="$task_tmp"
