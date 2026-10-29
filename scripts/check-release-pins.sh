#!/bin/bash
# Fails when a compose file still runs a moving tag (develop, latest, main),
# so a release never ships images that change after it is published.
#
#   ./scripts/check-release-pins.sh [compose file]
set -euo pipefail

compose=${1:-"$(cd "$(dirname "$0")/.." && pwd)/docker-compose.yml"}
fail=0

while read -r image; do
    repo=${image%%:*}
    tag=${image#*:}
    tag=${tag%%@*}
    case "${tag}" in
        develop|latest|main|master|nightly|"${image}"|"")
            echo "error: ${image} is a moving tag; pin it with scripts/pin-versions.sh" >&2
            fail=1
            ;;
    esac
done < <(grep -E "^[[:space:]]+image:" "${compose}" | sed -E 's/^[[:space:]]+image:[[:space:]]+//; s/[[:space:]]+$//')

[ "${fail}" -eq 0 ] && echo "every image in ${compose} is pinned to a release"
exit "${fail}"
