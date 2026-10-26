#!/bin/bash
# Prints the analyser Bridge release an OpenELIS-Global-2 release was built
# and tested with: the Bridge tag at the commit that release pins in
# tools/openelis-analyzer-bridge. Needs the GitHub CLI (gh), signed in or with
# GH_TOKEN set.
#
#   ./scripts/bridge-version-for.sh 3.3.0     # prints 3.4.1
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $0 <openelis version>" >&2
    exit 2
fi

oeVersion=$1
pin=$(gh api "repos/DIGI-UW/OpenELIS-Global-2/contents/tools/openelis-analyzer-bridge?ref=${oeVersion}" --jq .sha)
version=$(gh api --paginate repos/DIGI-UW/openelis-analyzer-bridge/tags --jq ".[] | select(.commit.sha == \"${pin}\") | .name" | head -n 1)

if [ -z "${version}" ]; then
    echo "error: OpenELIS ${oeVersion} pins Bridge commit ${pin}, which no Bridge release is tagged at; name the Bridge version yourself" >&2
    exit 1
fi
echo "${version}"
