#!/bin/bash
# Pins a compose file's images to an OpenELIS-Global-2 version and an analyser
# Bridge version. The two are released separately, so each is named.
#
#   ./scripts/pin-versions.sh <openelis version> <bridge version> [compose file]
#   ./scripts/pin-versions.sh 3.3.0 3.4.1
#   ./scripts/pin-versions.sh 3.3.0 3.4.1 OEDockerInstaller/stage/docker-compose.yml
#
# The OpenELIS images (webapp, frontend, database, FHIR, proxy) get the
# OpenELIS version. The Bridge gets itechuw/openelis-analyzer-bridge at the
# Bridge version, the image the Bridge's own release publishes. A Bridge
# version of "develop" keeps OpenELIS develop's own Bridge build instead,
# which always matches the Bridge revision develop pins.
# The compose file defaults to the repository's docker-compose.yml.
set -euo pipefail

if [ $# -lt 2 ]; then
    echo "usage: $0 <openelis version> <bridge version> [compose file]" >&2
    echo "  the Bridge release an OpenELIS release was built with: scripts/bridge-version-for.sh <openelis version>" >&2
    exit 2
fi

oeVersion=$1
bridgeVersion=$2
compose=${3:-"$(cd "$(dirname "$0")/.." && pwd)/docker-compose.yml"}

if [ "${bridgeVersion}" = "develop" ]; then
    bridgeImage="itechuw/openelis-global-2-analyzer-bridge:develop"
else
    bridgeImage="itechuw/openelis-analyzer-bridge:${bridgeVersion}"
fi

for repo in openelis-global-2 openelis-global-2-frontend openelis-global-2-database openelis-global-2-fhir openelis-global-2-proxy; do
    sed -E -i.bak "s#(image:[[:space:]]+)itechuw/${repo}:[^[:space:]]+#\1itechuw/${repo}:${oeVersion}#" "${compose}"
done
sed -E -i.bak "s#(image:[[:space:]]+)itechuw/openelis(-global-2)?-analyzer-bridge:[^[:space:]]+#\1${bridgeImage}#" "${compose}"
rm -f "${compose}.bak"

if ! grep -qE "image:[[:space:]]+${bridgeImage}[[:space:]]*$" "${compose}"; then
    echo "error: ${compose} has no analyser Bridge service to pin" >&2
    exit 1
fi
echo "pinned ${compose} to OpenELIS ${oeVersion} and analyser Bridge ${bridgeVersion}:"
grep -E "^[[:space:]]+image:" "${compose}" | sed -E 's/^[[:space:]]+image:[[:space:]]+/  /'
