#!/bin/sh
# Optional hook for a Red Hat EAP OpenShift image that supports postconfigure.
# Mount/copy configure-offline.sh into JBOSS_HOME/extensions as well.
set -eu
: "${JBOSS_HOME:?Set JBOSS_HOME}"
exec sh "$JBOSS_HOME/extensions/configure-offline.sh"
