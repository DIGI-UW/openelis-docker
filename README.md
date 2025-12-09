## OpenELIS Global2 Docker Compose Setup
Docker Compose setup for OpenELIS-Global2

You can find more information on how to set up OpenELIS at our [docs page](http://docs.openelis-global.org/)

[![Build Status](https://github.com/I-TECH-UW/OpenELIS-Global-2/actions/workflows/ci.yml/badge.svg)](https://github.com/I-TECH-UW/OpenELIS-Global-2/actions/workflows/ci.yml)

[![Publish Docker Image Status](https://github.com/I-TECH-UW/OpenELIS-Global-2/actions/workflows/publish-and-test.yml/badge.svg)](https://github.com/I-TECH-UW/OpenELIS-Global-2/actions/workflows/publish-and-test.yml)

[![Build Off Line Docker Images](https://github.com/I-TECH-UW/openelis-docker/actions/workflows/build-installer.yml/badge.svg)](https://github.com/I-TECH-UW/openelis-docker/actions/workflows/build-installer.yml)

## ONLINE INSTALLATION

## Updating the DB Passord (Optional)
1. Update the Enviroment vaiable `OE_DB_PASSWORD` in the [.env](./.env) file for the 'clinlims' user

1. Update the Enviroment vaiable `ADMIN_PASSWORD` in the [.env](./.env) file for the 'admin' user

### Running OpenELIS Global 3x with docker-compose
    docker-compose up -d

#### The Instance can be accessed at 

| Instance  |     URL       | credentials (user: password)|
|---------- |:-------------:|------:                       |
| OpeneELIS  |    https://localhost/  |  admin: adminADMIN!


## OFFLINE INSTALLTION

For offline Installtion,where theres no Intenet acess,

1. Download the  OpenELIS-Global Docker Installer zip file  from the [Release Artifacts](https://github.com/I-TECH-UW/openelis-docker/releases)

1. Unzip the OpenELIS-Global Docker Installer zip file 

       tar xzf OpenELIS-Global_<verion>_docker_installer.tar.gz

1. Move to directory of the Unziped OpenELIS-Global Docker Installer file 

       cd OpenELIS-Global_<verion>_docker_installer

1. For installing OpenELIS-Global2 the first time ,Load the images and start the containers  by running 

       ./run.sh

1. For Upgrading  OpenELIS-Global2 with an existing docker installer ,only Load the images form the new docker installer with the following command, update the image tags to the new docker installer version and re-satrt Global Global containers in your existing old Docker  installer

       ./upgrade.sh

       
    

