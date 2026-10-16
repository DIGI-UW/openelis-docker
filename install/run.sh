#!/bin/bash
# First installation: load the images shipped in this package, then start the
# stack without contacting any registry. Run it from the unpacked installer.
set -euo pipefail
cd "$(dirname "$0")"

echo "loading the images from dockerImage/openelis-images.tar.gz (this takes a few minutes)"
gunzip -c dockerImage/openelis-images.tar.gz | docker load

if docker compose version >/dev/null 2>&1; then
    docker compose up -d --pull never
else
    docker-compose up -d
fi
