#!/bin/bash
projectVersion=${1:-"latest"}
dockerVersion=${2:-"develop"} 

INSTALLER_CREATION_DIR="OEDockerInstaller"
CALL_DIR=$PWD

cd ${CALL_DIR}
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
    rm -r ${INSTALLER_CREATION_DIR}
fi

echo "creating docker images"

createLinuxInstaller() {
    context="OpenELIS-Global"
    installerName="${context}_${projectVersion}_docker_installer"

    echo "creating installer for context ${context}"
    mkdir -p ${INSTALLER_CREATION_DIR}/${installerName}/dockerImage
    mkdir -p ${INSTALLER_CREATION_DIR}/${installerName}/configs
    cp ./install/run.sh ${INSTALLER_CREATION_DIR}/${installerName}/run.sh
    cp ./install/upgrade.sh ${INSTALLER_CREATION_DIR}/${installerName}/upgrade.sh
    cp docker-compose.yml ${INSTALLER_CREATION_DIR}/${installerName}/docker-compose.yml
    cp .env ${INSTALLER_CREATION_DIR}/${installerName}/.env
    cp -r configs/* ${INSTALLER_CREATION_DIR}/${installerName}/configs
    cp OpenELIS-Global_DockerImage.tar.gz ${INSTALLER_CREATION_DIR}/${installerName}/dockerImage/OpenELIS-Global_DockerImage.tar.gz
    cp Postgres_DockerImage.tar.gz ${INSTALLER_CREATION_DIR}/${installerName}/dockerImage/Postgres_DockerImage.tar.gz
    cp JPAServer_DockerImage.tar.gz ${INSTALLER_CREATION_DIR}/${installerName}/dockerImage/JPAServer_DockerImage.tar.gz
    cp AutoHeal_DockerImage.tar.gz ${INSTALLER_CREATION_DIR}/${installerName}/dockerImage/AutoHeal_DockerImage.tar.gz
    cp NGINX_DockerImage.tar.gz ${INSTALLER_CREATION_DIR}/${installerName}/dockerImage/NGINX_DockerImage.tar.gz
    cp ReactFrontend_DockerImage.tar.gz ${INSTALLER_CREATION_DIR}/${installerName}/dockerImage/ReactFrontend_DockerImage.tar.gz
    cp Certs_DockerImage.tar.gz ${INSTALLER_CREATION_DIR}/${installerName}/dockerImage/Certs_DockerImage.tar.gz

    cd ${INSTALLER_CREATION_DIR}
    tar -cf ${installerName}.tar ${installerName}
    gzip ${installerName}.tar

    rm -r ${installerName}
    cd ${CALL_DIR}
}

cd ${CALL_DIR}
echo "saving docker image as OpenELIS-Global_DockerImage.tar.gz"
docker pull itechuw/openelis-global-2:${dockerVersion}
docker save itechuw/openelis-global-2:${dockerVersion} | gzip > OpenELIS-Global_DockerImage.tar.gz

echo "saving React frontend docker image"
docker pull itechuw/openelis-global-2-frontend:${dockerVersion}
docker save itechuw/openelis-global-2-frontend:${dockerVersion} | gzip > ReactFrontend_DockerImage.tar.gz

echo "saving JPA Server docker image"
docker pull itechuw/openelis-global-2-fhir:${dockerVersion}
docker save itechuw/openelis-global-2-fhir:${dockerVersion} | gzip > JPAServer_DockerImage.tar.gz

echo "saving Postgres docker image"
docker pull postgres:14.4
docker save postgres:14.4 | gzip > Postgres_DockerImage.tar.gz

echo "saving Autoheal docker image"
docker pull willfarrell/autoheal:1.2.0
docker save willfarrell/autoheal:1.2.0 | gzip > AutoHeal_DockerImage.tar.gz

echo "saving NGINX docker image"
docker pull itechuw/openelis-global-2-proxy:${dockerVersion}
docker save itechuw/openelis-global-2-proxy:${dockerVersion} | gzip > NGINX_DockerImage.tar.gz

echo "saving Certs docker image"
docker pull itechuw/certgen:main
docker save itechuw/certgen:main | gzip > Certs_DockerImage.tar.gz

cd ${CALL_DIR}
createLinuxInstaller 

rm OpenELIS-Global_DockerImage*.tar.gz
rm Postgres_DockerImage.tar.gz
rm JPAServer_DockerImage.tar.gz
rm AutoHeal_DockerImage.tar.gz
rm NGINX_DockerImage.tar.gz
rm ReactFrontend_DockerImage.tar.gz
rm Certs_DockerImage.tar.gz

