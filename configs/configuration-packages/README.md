# Configuration packages

A configuration package is a versioned ZIP of OpenELIS configuration files
(for example a test catalog) released outside this repository. Each
laboratory chooses its own packages, so none are pinned here.

## Pin a package

Put one JSON file per package in this folder, for example
`lab-catalog.json`, using the pin the package's release publishes:

```json
{
  "id": "lab-catalog",
  "version": "1.0.0",
  "url": "https://github.com/<owner>/<repository>/releases/download/v1.0.0/lab-catalog-1.0.0.zip",
  "sha256": "<SHA-256 of the ZIP>"
}
```

A pin has exactly these four string fields. `url` is an immutable HTTPS
release URL, or a GHCR digest `oci://ghcr.io/<owner>/<package>@sha256:<manifest digest>`
whose artifact has exactly one `application/zip` layer. `id` and `version`
must match the package's own manifest. A pin never holds credentials: for a
private GHCR package set `CONFIGURATION_REGISTRY_USERNAME` and
`CONFIGURATION_REGISTRY_TOKEN` in `.env`.

Then start as usual:

    docker compose up -d

## What happens at startup

The `configuration-packages` service runs
`scripts/prepare-configuration-packages.py` before OpenELIS starts. For each
pin it uses the verified copy in `configs/configuration-package-cache/` or
downloads the ZIP, checks its SHA-256 and manifest, and installs each file as
`configs/configuration/backend/<domain>/pkg--<id>--<version>--<filename>`.
OpenELIS then loads those files with its normal configuration loader. If
preparation fails, OpenELIS does not start; read why with
`docker compose logs configuration-packages`.

- Site files are never overwritten. An installed `pkg--` file that was edited,
  or any other conflict, stops startup with an error instead.
- A restart with unchanged pins uses the cache and needs no network.
- Without internet, copy the ZIP into `configs/configuration-package-cache/`
  named `<id>--<version>--<sha256>.zip`.
- To upgrade, change the pin's version, URL and SHA-256. Files and archives of
  earlier versions stay. Removing a pin removes neither its files nor the
  records OpenELIS created from them.
- Installing files is not importing records. Check the import summary
  OpenELIS logs for each file.

For each domain, OpenELIS reads either the files in `configs/configuration`
or its own built-in files, never both. A package file in a domain therefore
hides OpenELIS's built-in entries of that domain, so a package must carry every
section, sample type and dictionary entry its tests use.

## Package layout

The ZIP has a root `manifest.json`:

```json
{
  "format": "openelis-configuration/v1",
  "packageId": "catalog-name",
  "packageVersion": "1.0",
  "files": {
    "configuration/backend/dictionaries/catalog.csv": {
      "sha256": "<SHA-256 of this file>",
      "bytes": 123
    }
  }
}
```

Every other file in the ZIP is listed with its real size and SHA-256.
Configuration files live at `configuration/backend/<domain>/<filename>` and
are CSV, JSON, XML or properties files. Supporting material goes under
`evidence/`; it stays in the cache and is not installed. A package cannot add
a domain by itself: the OpenELIS release must have that domain's loader.
