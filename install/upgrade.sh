#!/bin/bash
# Upgrade of an existing installation: load the images shipped in this
# package. Then set the image tags in your current docker-compose.yml to
# this version (the images are listed in dockerImage/images.txt) and run
# `docker compose up -d` there.
set -euo pipefail
cd "$(dirname "$0")"

echo "loading the images from dockerImage/openelis-images.tar.gz (this takes a few minutes)"
gunzip -c dockerImage/openelis-images.tar.gz | docker load

echo "loaded:"
cat dockerImage/images.txt
echo "next: point the image tags in your existing docker-compose.yml at these images and run: docker compose up -d"
