#!/usr/bin/env bash
# Verify digest references survive export into an empty, disconnected daemon.
set -euo pipefail
archive=${1:?Image archive required}
references=${2:?Image reference list required}
engine_image=docker:29-dind@sha256:9e79b879b177fbd72c34376a3dd3d91747da5db49e1f560f76aea59561471977
# Pull the test infrastructure before disabling network access for the daemon.
docker pull "$engine_image"
name="oe-offline-verify-$$"
trap 'docker rm -fv "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --privileged --network none --name "$name" \
  -e DOCKER_TLS_CERTDIR= "$engine_image" >/dev/null
ready=false
for attempt in {1..30}; do
  if docker exec "$name" docker info >/dev/null 2>&1; then ready=true; break; fi
  sleep 1
done
[[ "$ready" = true ]] || { docker logs "$name"; exit 1; }
docker exec -i "$name" docker image load < "$archive"
while IFS= read -r image; do
  docker exec "$name" docker image inspect "$image" >/dev/null
  container=$(docker exec "$name" docker create --pull never --platform linux/amd64 \
    --network none --entrypoint /bin/true "$image")
  docker exec "$name" docker start -a "$container"
  docker exec "$name" docker rm "$container" >/dev/null
done < "$references"
