## OpenELIS Global2 Docker Compose Setup

Docker Compose setup for OpenELIS-Global2

You can find more information on how to set up OpenELIS at our [docs page](http://docs.openelis-global.org/)

[![Backend Build](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/backend.yml/badge.svg)](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/backend.yml)

[![Frontend Build](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/frontend.yml/badge.svg)](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/frontend.yml)

[![Publish Docker Images](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/publish-images.yml/badge.svg)](https://github.com/DIGI-UW/OpenELIS-Global-2/actions/workflows/publish-images.yml)

[![Validate distribution](https://github.com/DIGI-UW/openelis-docker/actions/workflows/validate-distribution.yml/badge.svg)](https://github.com/DIGI-UW/openelis-docker/actions/workflows/validate-distribution.yml)

## Install a release

Online and offline installations use the same Compose file, image digests,
credentials and key initialization. The only difference is how images reach Docker. Choose one download method below,
then configure credentials and use the matching startup command.

Use an x86-64 Linux host with Docker Engine 29 or later, Docker Compose, and the
[containerd image store](https://docs.docker.com/engine/storage/containerd/).
Fresh Docker 29 installations use that store by default. Verify before installing:

```sh
docker info --format '{{json .DriverStatus}}'
```

The output must contain `io.containerd.snapshotter.v1`. Offline archives need it to
retain the digest-pinned image identities. Upgraded Docker installations can still
use the classic store; changing stores hides existing images and containers, so
follow Docker's migration guidance separately from an OpenELIS upgrade. Docker,
Compose and host prerequisites must be installed before disconnecting the host;
the offline application package does not bundle operating-system packages.

### Obtain the release online

Select a [distribution release](https://github.com/DIGI-UW/openelis-docker/releases)
that includes `deployment-manifest.json`. Its Compose file already pins the exact
images tested and published together by OE2. Clone that tag, not the default branch:

```sh
# Replace <release> with the selected distribution release tag.
git clone --branch <release> --depth 1 https://github.com/DIGI-UW/openelis-docker.git openelis
cd openelis
```

The unreleased template refuses to start until an image set is selected. Only
for deliberate testing, set `OE_IMAGE_TAG=develop`; this does not select a stable
production release. Releases predating the manifest use their own tagged README.

For an offline host, use [the offline download](#obtain-the-release-offline)
instead of cloning or pulling images. Then use the same credential setup below.

### Obtain the release offline

On a connected computer, download `SHA256SUMS` and **all**
`openelis-<release>-linux-amd64.tar.gz.part-*` files from the same distribution
release. Transfer them together to the offline host. The parts keep each download
below GitHub's size limit; they are one application package, not separate installers.

Use a new, empty download directory. Substitute the chosen release number and run:

```sh
sha256sum -c SHA256SUMS
# Continue only when every part reports OK.
cat openelis-<release>-linux-amd64.tar.gz.part-* | tar -xz
cd openelis-<release>
docker image load -i images.tar
```

The extracted release has the same Compose file and settings as the online download.
Continue with the shared credential setup below. Keep the package for recovery;
`images.tar` is only needed when loading images into Docker.

### Configure installation credentials

Copy `.env.example` to `.env` and set different private values for
`OE_DB_PASSWORD`, `ADMIN_PASSWORD`, and `POSTGRES_PASSWORD`. These are required.
Create the initial application password file:

```sh
umask 077
cp .env.example .env
# Set the three database credentials in .env before continuing.
mkdir -p secrets
printf 'OEa1!%s\n' "$(openssl rand -hex 24)" > secrets/initial-admin-password
```

### Start an online installation

```sh
docker compose pull
docker compose up -d --no-build
docker compose ps
```

### Start an offline installation

```sh
docker compose up -d --pull never --no-build
docker compose ps
```

Missing images fail visibly instead of falling back to a registry or another version.

### Verify either installation

No setup script, host Java installation, manual certificate commands, or source
build is required. Docker manages the containers, persistent volumes and startup
dependencies. The one-shot `certs` service initializes installation keys before
consumers start; its successful `Exited (0)` state is expected. Check a startup
failure with `docker compose logs certs`. Do not remove volumes to clear an error.
Long-running services have restart policies for server reboots.

#### The instance can be accessed at

| Instance          |        URL         |                                   credentials (user: password) |
| ----------------- | :----------------: | -------------------------------------------------------------: |
| OpenELIS Frontend | https://localhost/ | `admin`, with the password in your local initial password file |

The application creates the administrator from the mounted password file only
when no administrator exists. Missing or invalid credentials stop fresh startup;
restarts and upgrades do not overwrite existing accounts. Retrieve the password
locally for first login and keep the file private. No password is baked into the
application image.

### Installation credentials

Create your private `.env` from [.env.example](./.env.example). Set the database credentials before the first start; the initial application password belongs in its separate secret file.

| Variable                                           | What it sets                                                                                                                                                                                             |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OE_DB_PASSWORD`                                   | Password of the `clinlims` database user the application connects with                                                                                                                                   |
| `ADMIN_PASSWORD`                                   | Password of the database administrator role, `admin`                                                                                                                                                     |
| `POSTGRES_PASSWORD`                                | Password of PostgreSQL's bootstrap account, `postgres`                                                                                                                                                   |
| `OE_INITIAL_ADMIN_PASSWORD_FILE`                   | Host path to the initial application password file; defaults to `./secrets/initial-admin-password`                                                                                                       |
| `SSL_KEYSTORE_PASSWORD`, `SSL_TRUSTSTORE_PASSWORD` | Passwords of the TLS stores. Set these before first start and retain them. An incorrect existing password stops initialization without rebuilding stores                                                 |
| `OE_ENCRYPTION_PASSWORD`                           | Leave empty for a fresh installation to use its generated `install/encryption.key`. Existing installations must preserve their effective old key; changing it makes stored connection secrets unreadable |

### Installation keys and existing installations

The `certs` image is released with OpenELIS and contains tools and the initializer,
not installation keys. `docker compose up -d` creates an independent TLS identity
and database-secret encryption key in empty volumes. The webapp, FHIR server and
proxy wait for initialization to finish. Restart retains the same keys. Incomplete
security volumes or incorrect passwords stop initialization; restore the complete
backup rather than deleting individual files to retry.

Follow [backup and restore](docs/backup-restore.md) and rehearse it before use.
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
and key using four environment variables in the [.env.example](./.env.example) file:

| Variable        | What it sets                                                                                                   | Default                 |
| --------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------- |
| `OE_CERTS_PATH` | **Where** the certificate directory comes from: a Docker named volume by default, or a host path in deployment | `certs-vol`             |
| `OE_KEYS_PATH`  | **Where** the private-key directory comes from                                                                 | `keys-vol`              |
| `OE_NGINX_CERT` | **Which** certificate file nginx loads from `OE_CERTS_PATH`                                                    | `apache-selfsigned.crt` |
| `OE_NGINX_KEY`  | **Which** key file nginx loads from `OE_KEYS_PATH`                                                             | `apache-selfsigned.key` |

- A bare name (e.g. `certs-vol`) uses the Docker **named volume** filled by the
  `certs` service. A value containing a slash (e.g. `/home/ubuntu/certs2026`) is
  mounted as a **host path** instead: put your real cert/key in that directory.
- `OE_NGINX_CERT` / `OE_NGINX_KEY` are the file names _inside_ those directories
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

The host ports are set in the [.env.example](./.env.example) file:

| Variable                                      | Service                              | Default        |
| --------------------------------------------- | ------------------------------------ | -------------- |
| `OE_HTTP_PORT`                                | proxy, HTTP (redirects to HTTPS)     | `80`           |
| `OE_HTTPS_PORT`                               | proxy, HTTPS: the address users open | `443`          |
| `OE_WEBAPP_HTTP_PORT`, `OE_WEBAPP_HTTPS_PORT` | webapp, published directly           | `8080`, `8443` |
| `OE_FHIR_HTTP_PORT`, `OE_FHIR_HTTPS_PORT`     | FHIR server, published directly      | `8081`, `8444` |

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

### Upgrades and recovery for either path

Back up the database, configuration, keys and Bridge state using
[the shared backup/restore procedure](docs/backup-restore.md). Retain installation
credentials and data when changing releases. Online hosts pull the selected new
release; offline hosts load its image archive. Both then use that release's Compose
file and existing settings. Apply the documented existing-installation adoption
step only when required; offline delivery does not change encryption or migration
semantics. Do not extract a fresh package over a live installation or delete volumes
to force initialization.

Previously published offline installers retain their original tagged instructions.
Their scripts are not used for these manifest-based releases.

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
  `ANALYZER_BRIDGE_PAIRING_CODE` from `.env`. Generate a private value
  before the first start, for example with `openssl rand -hex 24`. To pair again (for example after
  the Bridge's volume was deleted), choose **Pair again** on the Analysers
  page and enter the code from `.env`.
- An online installation started with `docker compose up -d` has no code
  until you set one: put a private random value in `ANALYZER_BRIDGE_PAIRING_CODE` in
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

## Publishing a distribution

OE2 owns image builds, tests and publication. This repository packages configuration
and consumes OE2's `deployment-manifest.json`; it does not build application images
or select an independent Bridge version.

After the OE2 release has its manifest, run
[Publish tested distribution](https://github.com/DIGI-UW/openelis-docker/actions/workflows/release-distribution.yml)
on `main` with that release version. The workflow checks the manifest against the
OE2 tag's commit, writes its image digests into Compose and creates a distribution
tag of the same version. The mock image remains in the source manifest for evidence
but is not installed in a lab. A retry verifies an existing tag; it never moves it
or replaces a release asset. The same workflow exports those images, verifies
loading and executing them by digest in an empty, disconnected Docker daemon, and
attaches the offline package and checksums. Application workflows still need their
normal acceptance tests; the transfer check runs only a no-op command in each image.
A changed image set requires a new OE2 release. A complete existing offline package
is verified and retained on retry. An interrupted upload without `SHA256SUMS` is
incomplete and needs explicit recovery; retries never overwrite uploaded parts.

The initial manifest-enabled OE2 images must be published before this workflow can
produce a usable distribution. Older releases without that manifest cannot use it.
Current releases follow reviewed `main` commits; supported older maintenance lines
retain their OE2 release-policy exception.

The OE2 **Publish images / Deploy testing** workflow is the sole owner of the shared
testing server. This repository has no second server-deployment workflow. Local
source development remains in OE2's development launcher; normal installations use
Docker Compose and published images.

### Adopting private initial credentials on an existing installation

Retain the database volume and existing role passwords. Set `POSTGRES_PASSWORD`
to the value previously used in `configs/database/database.env`; environment
changes do not rotate existing roles. Compose requires a mountable initial
password file even when an administrator already exists. For that case, an empty
file is sufficient: the application does not read it or alter the existing login.
Do not delete volumes to force initialization. Previously shared passwords need
an explicit rotation; this upgrade does not claim to rotate them.

The distribution contains only `.env.example`, never an installation's `.env`.
Use matching application and database releases that support these credentials.
Hashed administrator password files are not supported.
