## OpenELIS Global2 Docker Compose Setup
Docker Compose setup for OpenELIS-Global2

You can find more information on how to set up OpenELIS at our [docs page](http://docs.openelis-global.org/)

[![Backend Build](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/backend.yml/badge.svg)](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/backend.yml)

[![Frontend Build](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/frontend.yml/badge.svg)](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/frontend.yml)

[![Publish Docker Images](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/publish-images.yml/badge.svg)](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/publish-images.yml)

[![Build Off Line Docker Images](https://github.com/DIGI-UW/openelis-docker/actions/workflows/build-installer.yml/badge.svg)](https://github.com/DIGI-UW/openelis-docker/actions/workflows/build-installer.yml)

## ONLINE INSTALLATION

### Running OpenELIS Global with Docker Compose

Use a released version of this repository, which pins matching application and
support images. The `main` branch tracks development images and is for testing.
Configure `.env` before the first start, then use Docker Compose directly:

```sh
docker compose pull
docker compose up -d --no-build
docker compose ps
```

No setup script, host Java installation, manual certificate commands, or source
build is required. Docker manages the containers, persistent volumes and startup
dependencies. The one-shot `certs` service initializes installation keys before
consumers start; its successful `Exited (0)` state is expected. Check a startup
failure with `docker compose logs certs`. Do not remove volumes to clear an error.
Long-running services have restart policies for server reboots.

#### The instance can be accessed at

| Instance  |     URL       | credentials (user: password)|
|---------- |:-------------:|------:                       |
| OpenELIS Frontend  |    https://localhost/  |  admin: adminADMIN!

The application's admin password starts as the `DEFAULT_PW` set in
[docker-compose.yml](./docker-compose.yml) and is changed inside OpenELIS after
the first login.

### Passwords (Optional)

All of these live in the [.env](./.env) file. Set them before the first start.

| Variable | What it sets |
|----------|--------------|
| `OE_DB_PASSWORD` | Password of the `clinlims` database user the application connects with |
| `ADMIN_PASSWORD` | Password of the database superuser (`postgres`). It is not the application's admin user |
| `SSL_KEYSTORE_PASSWORD`, `SSL_TRUSTSTORE_PASSWORD` | Passwords of the TLS stores. Set these before first start and retain them. An incorrect existing password stops initialization without rebuilding stores |
| `OE_ENCRYPTION_PASSWORD` | Leave empty for a fresh installation to use its generated `install/encryption.key`. Existing installations must preserve their effective old key; changing it makes stored connection secrets unreadable |

### Installation keys and existing installations

The `certs` image is released with OpenELIS and contains tools and the initializer,
not installation keys. `docker compose up -d` creates an independent TLS identity
and database-secret encryption key in empty volumes. The webapp, FHIR server and
proxy wait for initialization to finish. Restart retains the same keys. Incomplete
security volumes or incorrect passwords stop initialization; restore the complete
backup rather than deleting individual files to retry.

Back up the database, `key_trust-store-volume`, `keys-vol`, `certs-vol`, `.env`, and
any externally managed certificates together. Keep backups private. The internal
private stores are readable by the existing Tomcat TLS group (8443). The public
truststore is also readable by the Bridge. The installation key directory and
proxy private key are restricted to the root initialization processes.

**Existing installations require a separate adoption step.** Take and verify a
backup, stop application consumers, and retain the effective encryption password
already used by that installation in `OE_ENCRYPTION_PASSWORD`. Do not guess it or
replace it with a new random value. Earlier versions sometimes used the keystore
password; check the site's effective configuration. With that value exported in
the shell without putting it on the command line, run:

```sh
docker compose run --rm -e OE_ENCRYPTION_PASSWORD certs --upgrade-existing
docker compose up -d
```

Adoption replaces a recognized old shared TLS identity, preserves site-owned
certificates and other trusted partners, and records the existing encryption key
if no installation key file exists. It does not convert encrypted database values.
Ordinary startup never invokes this command. Planned replacement of an internal
keystore also requires explicit adoption; externally managed proxy certificates
remain under the operator's control.

This candidate requires the corresponding OE2 certificate-tool release. Do not
mix it with an older application image that cannot load the installation key.

### Configuring the TLS Certificate (Optional)

By default the proxy serves the self-signed certificate generated by the `certs`
service. For a real deployment you can point the proxy at your own certificate
and key using four environment variables in the [.env](./.env) file:

| Variable | What it sets | Default |
|----------|--------------|---------|
| `OE_CERTS_PATH` | **Where** the certificate directory comes from: a Docker named volume by default, or a host path in deployment | `certs-vol` |
| `OE_KEYS_PATH`  | **Where** the private-key directory comes from | `keys-vol` |
| `OE_NGINX_CERT` | **Which** certificate file nginx loads from `OE_CERTS_PATH` | `apache-selfsigned.crt` |
| `OE_NGINX_KEY`  | **Which** key file nginx loads from `OE_KEYS_PATH` | `apache-selfsigned.key` |

- A bare name (e.g. `certs-vol`) uses the Docker **named volume** filled by the
  `certs` service. A value containing a slash (e.g. `/home/ubuntu/certs2026`) is
  mounted as a **host path** instead: put your real cert/key in that directory.
- `OE_NGINX_CERT` / `OE_NGINX_KEY` are the file names *inside* those directories
  (a relative path inside them also works); nginx is rendered to load them at
  startup, so they must match the files present.

Example: serving real certs from `/home/ubuntu/certs2026/cert.crt` and `cert.key`:

    OE_CERTS_PATH=/home/ubuntu/certs2026
    OE_KEYS_PATH=/home/ubuntu/certs2026
    OE_NGINX_CERT=cert.crt
    OE_NGINX_KEY=cert.key

Let's Encrypt: do not point the paths at `/etc/letsencrypt/live/<domain>`. Its
files are symlinks into `../../archive/<domain>`, which does not exist inside
the container, and the proxy fails with "cannot load certificate". Either copy
the files out as regular files (for example from a certbot deploy hook that
runs `cp -L` into `/etc/openelis-certs`) and point the paths there, or mount
the whole tree and name the files by their path inside it:

    OE_CERTS_PATH=/etc/letsencrypt
    OE_KEYS_PATH=/etc/letsencrypt
    OE_NGINX_CERT=live/example.org/fullchain.pem
    OE_NGINX_KEY=live/example.org/privkey.pem

### Ports and Reverse Proxies (Optional)

The host ports are set in the [.env](./.env) file:

| Variable | Service | Default |
|----------|---------|---------|
| `OE_HTTP_PORT` | proxy, HTTP (redirects to HTTPS) | `80` |
| `OE_HTTPS_PORT` | proxy, HTTPS: the address users open | `443` |
| `OE_WEBAPP_HTTP_PORT`, `OE_WEBAPP_HTTPS_PORT` | webapp, published directly | `8080`, `8443` |
| `OE_FHIR_HTTP_PORT`, `OE_FHIR_HTTPS_PORT` | FHIR server, published directly | `8081`, `8444` |

To serve OpenELIS on 8080 and 8443, move the webapp's own ports out of the
way first, then run `docker compose up -d`:

    OE_HTTP_PORT=8080
    OE_HTTPS_PORT=8443
    OE_WEBAPP_HTTP_PORT=18080
    OE_WEBAPP_HTTPS_PORT=18443

Users then open `https://<server>:8443/`, and `http://<server>:8080/`
redirects there.

Behind another reverse proxy (a gateway, a load balancer), have that proxy
pass the address users opened, either with the standard `Forwarded` header or
with `X-Forwarded-Proto`, `X-Forwarded-Host` and `X-Forwarded-Port`. For
nginx:

    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Port $server_port;

A gateway that rewrites `Host` to the OpenELIS server's name (Apache's
`ProxyPass` without `ProxyPreserveHost On`) works too, because it sends the
original host in `X-Forwarded-Host`. Connect the gateway to the HTTPS port:
the HTTP port only redirects to `OE_HTTPS_PORT`.

OpenELIS uses them for the links it builds (the login redirect, single
sign-on callbacks, FHIR links), so they keep a port such as 8443. It reads
them only from connections on a private network or loopback address, where
its own proxy sits. This needs OpenELIS-Global-2 3.4.0 or later.

## OFFLINE INSTALLATION

Every OpenELIS-Global-2 release has a matching openelis-docker release with an
offline package attached, built by the
[Build OpenELIS-Global-2 Offline Docker Images](https://github.com/DIGI-UW/openelis-docker/actions/workflows/build-installer.yml)
workflow. The package holds the compose file pinned to an OpenELIS-Global-2
version and an analyser Bridge version, the configuration files, the install
scripts and `dockerImage/openelis-images.tar.gz` with every image the compose
file runs; `dockerImage/images.txt` lists them, and the release notes name
both versions.

1. Download `OpenELIS-Global_<version>_docker_installer.tar.gz` from the
   [releases](https://github.com/DIGI-UW/openelis-docker/releases)

1. Unpack it

       tar xzf OpenELIS-Global_<version>_docker_installer.tar.gz

1. Move into the unpacked directory

       cd OpenELIS-Global_<version>_docker_installer

1. For a first installation, load the images and start the containers. The
   stack starts with `docker compose up -d --pull never`, so no registry is
   contacted

       ./run.sh

1. For upgrading an existing installation, give the upgrade script the
   directory of that installation. It loads the images, replaces the
   installation's `docker-compose.yml` with the package's (the old one is
   kept next to it as `docker-compose.yml.<date>.bak`), adds the
   configuration folders this version needs without touching the ones you
   have, updates `configs/nginx/nginx.conf` when it is one this project
   shipped (the old one is kept as `nginx.conf.<date>.bak`; a file you edited
   is left as it is), adds the analyser Bridge pairing code to your `.env`,
   and restarts the stack there without contacting any registry

       ./upgrade.sh /path/to/your/installation

   If you had changed your `docker-compose.yml` (extra volumes, other ports),
   carry those changes over from the backup; ports now go in `.env` (see
   Ports and Reverse Proxies). Your `.env` is kept: the package's
   `.env` carries the default passwords, and `OE_ENCRYPTION_PASSWORD` must
   stay what it was (your keystore password, when it was never set) or the
   connection passwords saved in OpenELIS stop decrypting.

   `./upgrade.sh` with no directory only loads the images; you then update the
   tags in your `docker-compose.yml` to the versions in
   `dockerImage/images.txt`, add the `openelis-analyzer-bridge` service and
   the `bridge-state` volume from the package's `docker-compose.yml`, copy
   `configs/analyzer-imports/`, and complete the explicit key adoption above before running
   `docker compose up -d` there.

## LIGHT INSTALLATION

A lab that needs no integration with other systems can run OpenELIS without
the FHIR server and the analyser Bridge. Every lab workflow (patients, orders,
sample preparation and labels, results, validation, reports, non-conformities,
storage, administration) runs from the OpenELIS database alone. The two
services only serve exchanges with the outside: analysers (through the
Bridge), electronic orders from an EMR or a consolidated server, referrals to
and results from other laboratories, EQA exchange, sample shipments and the
client registry. Questionnaires are kept in the database when there is no FHIR
store.

In [.env](./.env), remove the `#` in front of this line, then start as usual:

    COMPOSE_FILE=docker-compose.yml:docker-compose.light.yml

    docker compose up -d

That is all: `docker-compose.light.yml` scales the two services to zero and
clears the FHIR store and the Bridge address on the webapp, and the offline
package's `run.sh` and `upgrade.sh` honour the same line. The Analysers page
then shows no analysers (from the release after 3.3.0 it says that no Bridge
address is configured).

The same two steps switch an installation that already runs the full stack:
`docker compose up -d` removes the two containers and the database is
untouched. Put the `#` back and run `docker compose up -d` to return to the
full stack.

## ANALYSERS

Analysers connect to the analyser Bridge (`openelis-analyzer-bridge`), which
the stack starts with OpenELIS; the Analysers pages in OpenELIS set them up
through it. Since 3.3.0 the Bridge is the only way analysers reach OpenELIS.

- OpenELIS pairs with the Bridge when it starts, using
  `ANALYZER_BRIDGE_PAIRING_CODE` from `.env`. `run.sh` and `upgrade.sh`
  generate that code for each installation. To pair again (for example after
  the Bridge's volume was deleted), choose **Pair again** on the Analysers
  page and enter the code from `.env`.
- An online installation started with `docker compose up -d` has no code
  until you set one: put any value in `ANALYZER_BRIDGE_PAIRING_CODE` in
  `.env` before the first start, or enter the code the Bridge logs
  (`docker logs openelis-analyzer-bridge`) on the Analysers page.
- Analysers on the lab network send to the host on port 12001 (ASTM LIS01-A
  over TCP), 12011 (ASTM E1381) or 2575 (HL7 v2 over MLLP). File-based
  analysers drop their result files into a folder under
  `configs/analyzer-imports/`, named on the analyser's page. The Bridge runs
  as its own user (`astm`, uid 9257) and creates each analyser's folder there,
  so `configs/analyzer-imports/` must let other users write. `run.sh` and
  `upgrade.sh` set that; an online installation does it once before the first
  start:

      chmod 1777 configs/analyzer-imports
- The Bridge keeps its certificate, the pairing, the analyser connections and
  the results OpenELIS has not accepted yet in the `bridge-state` volume.
  Keep that volume across upgrades.

Upgrading from 3.2.x: the analyser settings of the old analyser module
(connection, file import and test mappings) are not carried over. The upgrade
writes all of them into the database before removing them, and each analyser
has to be set up again on the Analysers pages. Save that export to a file once
the upgraded stack is up:

    docker exec openelisglobal-database psql -U clinlims -d clinlims -At \
      -c "select summary from clinlims.configuration_import_run where source = 'ANALYZER_LEGACY'" \
      > legacy-analyzers.json

It holds, under `analyzers`, each analyser's old settings by column name, and
under each removed table's name (for example `analyzer_test_map`) its rows.
Note your analysers' addresses and test codes before you upgrade as well.

## RELEASING

OpenELIS-Global-2 and the analyser Bridge
([openelis-analyzer-bridge](https://github.com/DIGI-UW/openelis-analyzer-bridge))
are released separately and have their own version numbers, so every release
here names both. `docker-compose.yml` on `main` runs the `:develop` images,
including OpenELIS develop's own Bridge build
(`itechuw/openelis-global-2-analyzer-bridge:develop`); a release pins the
OpenELIS images to the OpenELIS version and the Bridge to
`itechuw/openelis-analyzer-bridge:<bridge version>`.

To release, open the
[Build OpenELIS-Global-2 Offline Docker Images](https://github.com/DIGI-UW/openelis-docker/actions/workflows/build-installer.yml)
workflow, choose Run workflow and enter:

- `version`: the OpenELIS-Global-2 release tag, for example `3.3.0`. It is
  also the version of the release here.
- `bridge_version`: the analyser Bridge release to ship with it, for example
  `3.4.1`. Use the Bridge release that OpenELIS version was built and tested
  with; this prints it:

      ./scripts/bridge-version-for.sh 3.3.0

The workflow checks that every image exists on Docker Hub, pins
`docker-compose.yml` to both versions (`scripts/pin-versions.sh`), refuses any
moving tag left (`scripts/check-release-pins.sh`), commits and tags the
result, creates the release when it does not exist, then builds the package
with the same two versions and attaches it. It releases from `main` (or the
branch or commit given as `base_ref`), so running it again for an existing
version moves that tag onto the current packaging and replaces the package.
The workflow also
runs when a release is published here, and once a day for the latest
OpenELIS-Global-2 release that still has no package; those runs take the
Bridge release OpenELIS was built with, and warn when a version given by hand
differs from it.

To build a package yourself, run `./build.sh <openelis version> <bridge version>`,
for example `./build.sh 3.3.0 3.4.1` (or `./build.sh develop develop` for a
test package of the develop images). It pins a copy of `docker-compose.yml` to
both versions, pulls every image that copy names, saves them into one archive
and writes the installer to `OEDockerInstaller/`.
