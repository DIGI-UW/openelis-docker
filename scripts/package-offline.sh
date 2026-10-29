#!/usr/bin/env bash
# Release packaging only. Operators use docker load and docker compose directly.
set -euo pipefail
cd "$(dirname "$0")/.."
output=${1:?Usage: scripts/package-offline.sh /absolute/new-output-directory}
[[ "$output" = /* ]] || { echo 'Output directory must be absolute' >&2; exit 1; }
git diff --quiet && git diff --cached --quiet || { echo 'Commit the release configuration first' >&2; exit 1; }
git cat-file -e HEAD:deployment-manifest.json
version=$(python3 -c 'import json; print(json.load(open("deployment-manifest.json"))["appBranch"])')
commit=$(python3 -c 'import json; print(json.load(open("deployment-manifest.json"))["appSha"])')
python3 scripts/apply-release-manifest.py deployment-manifest.json "$version" "$commit" --check
docker info --format '{{json .DriverStatus}}' | grep -q io.containerd.snapshotter.v1 || {
  echo 'Offline digest-preserving archives require the Docker containerd image store' >&2; exit 1;
}
mkdir "$output"
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
# Export tracked release files only: never include local .env, credentials or data.
git archive --prefix="openelis-$version/" HEAD | tar -xf - -C "$staging"
bundle="$staging/openelis-$version"
# Compose requires credentials to render configuration. These throwaway values
# only enumerate images; no containers or credential files are created here.
offline_validation_value=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
OE_DB_PASSWORD="$offline_validation_value" ADMIN_PASSWORD="$offline_validation_value" POSTGRES_PASSWORD="$offline_validation_value" ANALYZER_BRIDGE_PAIRING_CODE="$offline_validation_value" \
  docker compose --env-file "$bundle/.env.example" -f "$bundle/docker-compose.yml" config --images \
  | LC_ALL=C sort -u > "$bundle/images.txt"
images=()
while IFS= read -r image; do
  [[ "$image" =~ @sha256:[a-f0-9]{64}$ ]] || { echo "Unpinned image: $image" >&2; exit 1; }
  docker pull --platform linux/amd64 "$image"
  # A name in the original repository lets Docker restore its RepoDigest.
  # Digest-only export loses that name; these local aliases are never published.
  repository=${image%@*}
  alias="${repository%%:*}:offline-${image##*@sha256:}"
  docker tag "$image" "$alias"
  images+=("$alias")
done < "$bundle/images.txt"
[[ ${#images[@]} -gt 0 ]]
# Preserve the original image index: save --platform rewrites it and drops pins.
docker image save -o "$bundle/images.tar" "${images[@]}"
# Exercise the exported archive in an empty Docker daemon with no network.
bash tests/offline-roundtrip.sh "$bundle/images.tar" "$bundle/images.txt"
# Release assets must each be below GitHub's 2 GiB limit; standard split/cat
# avoids another archive format or an operator-side assembly script.
tar -C "$staging" -cf - "openelis-$version" | gzip -n | \
  split -b 1024m - "$output/openelis-$version-linux-amd64.tar.gz.part-"
python3 - "$output" <<'CHECKSUMS'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
with (root / 'SHA256SUMS').open('w') as sums:
    for part in sorted(root.glob('*.part-*')):
        with part.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        sums.write(f'{digest}  {part.name}\n')
CHECKSUMS
