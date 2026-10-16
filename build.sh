#!/bin/bash
# Builds the offline installer: the compose file with its image tags pinned
# to dockerVersion, .env, configs, the install scripts and one archive holding
# every image the compose file runs. The image list is read from the compose
# file itself, so the package cannot miss an image the stack needs.
# Usage: ./build.sh <projectVersion> <dockerVersion>
set -euo pipefail

projectVersion=${1:-"latest"}
dockerVersion=${2:-"develop"}

INSTALLER_CREATION_DIR="OEDockerInstaller"
IMAGES_ARCHIVE="openelis-images.tar.gz"
# The checkout this script lives in, so it works from any directory.
CALL_DIR=$(cd "$(dirname "$0")" && pwd)
# The published images are amd64; pull and save that platform whatever the
# build machine is (arm64 hosts, containerd image store).
export DOCKER_DEFAULT_PLATFORM=linux/amd64

cd "${CALL_DIR}"
if [ -d "${INSTALLER_CREATION_DIR}" ]
then
    while true; do
        read -p "Installer directory has been detected, replace it? [Y]es [N]o: " yn
        case $yn in
            [Yy][Ee][Ss]|[Yy] ) break;;
            [Nn][Oo]|[Nn] ) exit;;
            * ) echo "Please answer yes or no.";;
        esac
    done
    rm -r "${INSTALLER_CREATION_DIR}"
fi

context="OpenELIS-Global"
installerName="${context}_${projectVersion}_docker_installer"
stageDir="${INSTALLER_CREATION_DIR}/${installerName}"

echo "creating installer for context ${context}"
mkdir -p "${stageDir}/dockerImage" "${stageDir}/configs"
cp ./install/run.sh "${stageDir}/run.sh"
cp ./install/upgrade.sh "${stageDir}/upgrade.sh"
# Pin every :develop image to the requested version; a compose file that is
# already pinned (release tags carry one) is copied unchanged.
sed "s/:develop[[:space:]]*$/:${dockerVersion}/" docker-compose.yml > "${stageDir}/docker-compose.yml"
cp .env "${stageDir}/.env"
cp -r configs/* "${stageDir}/configs"

images=$(docker compose --project-directory "${CALL_DIR}" -f "${stageDir}/docker-compose.yml" config --images | sort -u)
echo "images in docker-compose.yml:"
echo "${images}"
echo "${images}" > "${stageDir}/dockerImage/images.txt"

echo "pulling the images"
for image in ${images}; do
    docker pull "${image}"
done

platformFlag=""
if docker save --help 2>&1 | grep -q -- '--platform'; then
    platformFlag="--platform ${DOCKER_DEFAULT_PLATFORM}"
else
    # Older CLIs cannot pick a platform at save time, and with the containerd
    # image store a tag that names a multi-platform index cannot be saved
    # when only one platform was pulled. Point each such tag at its amd64
    # manifest instead, so docker save exports exactly that image.
    for image in ${images}; do
        digest=$(docker buildx imagetools inspect "${image}" --format \
            '{{range .Manifest.Manifests}}{{if and (eq .Platform.OS "linux") (eq .Platform.Architecture "amd64")}}{{.Digest}}{{end}}{{end}}' \
            2>/dev/null || true)
        if [ -n "${digest}" ]; then
            docker pull --platform "${DOCKER_DEFAULT_PLATFORM}" "${image%%:*}@${digest}" >/dev/null
            docker tag "${image%%:*}@${digest}" "${image}"
        fi
    done
fi
echo "saving the images as dockerImage/${IMAGES_ARCHIVE}"
# shellcheck disable=SC2086
docker save ${platformFlag} ${images} | gzip > "${stageDir}/dockerImage/${IMAGES_ARCHIVE}"

cd "${INSTALLER_CREATION_DIR}"
tar -cf "${installerName}.tar" "${installerName}"
gzip "${installerName}.tar"
rm -r "${installerName}"
cd "${CALL_DIR}"
echo "installer: ${INSTALLER_CREATION_DIR}/${installerName}.tar.gz"
