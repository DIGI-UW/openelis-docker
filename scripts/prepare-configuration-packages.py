#!/usr/bin/env python3
"""Install checksum-pinned configuration packages into the OpenELIS configuration tree.

Nothing is imported here: OpenELIS loads the installed files with its normal
configuration loader. Files under evidence/ stay in the cached archive.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile

FORMAT = "openelis-configuration/v1"
MAX_BYTES = 128 * 1024 * 1024
NAME = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_pin(path):
    pin = json.loads(path.read_text())
    if set(pin) != {"id", "version", "url", "sha256"}:
        raise ValueError("Package pin requires id, version, url and sha256")
    if any(not isinstance(pin[k], str) for k in pin):
        raise ValueError("Package pin values must be strings")
    if not re.fullmatch(NAME, pin["id"]) or not re.fullmatch(NAME, pin["version"]):
        raise ValueError("Invalid package id or version")
    if not re.fullmatch(r"[a-f0-9]{64}", pin["sha256"]):
        raise ValueError("Package requires a reviewed SHA-256")
    url = urllib.parse.urlsplit(pin["url"])
    if url.scheme == "oci":
        oci_reference(pin["url"])
    elif url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError("Package URL must be HTTPS or digest-pinned GHCR OCI without credentials")
    return pin


def configuration_files(content, pin):
    if len(content) > MAX_BYTES:
        raise ValueError("Package exceeds size limit")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = archive.infolist()
        names = [e.filename for e in entries]
        if len(set(names)) != len(names) or names.count("manifest.json") != 1:
            raise ValueError("Duplicate archive entries or missing manifest")
        if sum(e.file_size for e in entries) > MAX_BYTES:
            raise ValueError("Expanded package exceeds size limit")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename
                    or str(path) != entry.filename or entry.is_dir()
                    or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not stat.S_ISREG(mode))):
                raise ValueError("Unsafe archive entry: " + entry.filename)
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("format") != FORMAT or manifest.get("packageId") != pin["id"]
                or manifest.get("packageVersion") != pin["version"]):
            raise ValueError("Package manifest differs from pin")
        inventory = manifest.get("files", {})
        if set(inventory) != set(names) - {"manifest.json"}:
            raise ValueError("Manifest inventory mismatch")
        installed = {}
        for name, expected in inventory.items():
            data = archive.read(name)
            if expected.get("bytes") != len(data) or expected.get("sha256") != digest(data):
                raise ValueError("Payload checksum mismatch: " + name)
            parts = PurePosixPath(name).parts
            if parts[0] == "evidence":
                continue
            if (len(parts) != 4 or parts[:2] != ("configuration", "backend")
                    or not re.fullmatch(NAME, parts[2]) or not re.fullmatch(NAME, parts[3])
                    or PurePosixPath(name).suffix not in {".csv", ".json", ".xml", ".properties"}):
                raise ValueError("Unsupported configuration path: " + name)
            # The reserved prefix never overwrites site files and keeps older versions.
            filename = "pkg--" + pin["id"] + "--" + pin["version"] + "--" + parts[3]
            installed[Path("backend") / parts[2] / filename] = data
        if not installed:
            raise ValueError("Package contains no configuration files")
        return installed


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise ValueError("Package download refused a non-HTTPS redirect")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


def download(url, target):
    if url.startswith("oci:"):
        return download_oci(url, target)
    opener = urllib.request.build_opener(HTTPSRedirects())
    with opener.open(url, timeout=60) as response, target.open("wb") as output:
        size = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("Package exceeds size limit")
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())


def oci_reference(url):
    parsed = urllib.parse.urlsplit(url)
    match = re.fullmatch(r"/([a-z0-9][a-z0-9._/-]*)@sha256:([a-f0-9]{64})", parsed.path)
    if (parsed.scheme != "oci" or parsed.netloc != "ghcr.io" or not match
            or parsed.query or parsed.fragment or ".." in parsed.path):
        raise ValueError("OCI package must be ghcr.io/repository@sha256:<digest>")
    return match.group(1), match.group(2)


def registry_bytes(url, headers, limit):
    opener = urllib.request.build_opener(HTTPSRedirects())
    with opener.open(urllib.request.Request(url, headers=headers), timeout=60) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Registry response exceeds size limit")
    return content


def download_oci(url, target):
    repository, manifest_digest = oci_reference(url)
    headers = {}
    username = os.environ.get("CONFIGURATION_REGISTRY_USERNAME", "")
    password = os.environ.get("CONFIGURATION_REGISTRY_TOKEN", "")
    if bool(username) != bool(password):
        raise ValueError("Private packages require both registry username and token")
    if username:
        headers["Authorization"] = "Basic " + base64.b64encode(
            (username + ":" + password).encode()).decode()
    token_url = "https://ghcr.io/token?" + urllib.parse.urlencode({
        "service": "ghcr.io", "scope": "repository:" + repository + ":pull"})
    token = json.loads(registry_bytes(token_url, headers, 65536))["token"]
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/vnd.oci.image.manifest.v1+json"}
    base = "https://ghcr.io/v2/" + repository
    raw = registry_bytes(base + "/manifests/sha256:" + manifest_digest, headers, 1024 * 1024)
    if digest(raw) != manifest_digest:
        raise ValueError("OCI manifest differs from immutable pin")
    manifest = json.loads(raw)
    layers = manifest.get("layers", [])
    if (manifest.get("schemaVersion") != 2 or len(layers) != 1
            or layers[0].get("mediaType") != "application/zip"):
        raise ValueError("Configuration artifact must have exactly one ZIP layer")
    layer = layers[0]
    if (not re.fullmatch(r"sha256:[a-f0-9]{64}", layer.get("digest", ""))
            or not isinstance(layer.get("size"), int) or not 0 < layer["size"] <= MAX_BYTES):
        raise ValueError("Invalid configuration layer descriptor")
    content = registry_bytes(base + "/blobs/" + layer["digest"], headers, MAX_BYTES)
    if len(content) != layer["size"] or "sha256:" + digest(content) != layer["digest"]:
        raise ValueError("OCI layer differs from manifest")
    with target.open("wb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def prepare(pin_path, cache, configuration, fetch=download):
    pin = read_pin(pin_path)
    configuration = configuration.resolve()
    cache = cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    archive_path = cache / (pin["id"] + "--" + pin["version"] + "--" + pin["sha256"] + ".zip")
    content = archive_path.read_bytes() if archive_path.is_file() and archive_path.stat().st_size <= MAX_BYTES else b""
    if digest(content) != pin["sha256"]:
        fd, name = tempfile.mkstemp(prefix=".download-", dir=cache)
        os.close(fd)
        temporary = Path(name)
        try:
            fetch(pin["url"], temporary)
            if temporary.stat().st_size > MAX_BYTES:
                raise ValueError("Package exceeds size limit")
            content = temporary.read_bytes()
            if digest(content) != pin["sha256"]:
                raise ValueError("Package checksum differs from pin")
            configuration_files(content, pin)
            temporary.chmod(0o644)
            os.replace(temporary, archive_path)
        finally:
            temporary.unlink(missing_ok=True)
    files = configuration_files(content, pin)
    configuration.mkdir(parents=True, exist_ok=True)
    # Validate every destination before writing anything. Never follow a symlink
    # or replace a local customization, including an edited managed file.
    for relative, data in files.items():
        target = configuration / relative
        if any(p.is_symlink() for p in (target, *target.parents)):
            raise ValueError("Symlink in configuration destination: " + str(target))
        if target.exists() and (not target.is_file() or target.read_bytes() != data):
            raise ValueError("Configuration conflict; existing file preserved: " + str(target))
    created = []
    try:
        for relative, data in files.items():
            target = configuration / relative
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=".package-", dir=target.parent)
            temporary = Path(name)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                temporary.chmod(0o644)
                # Link is an atomic no-overwrite publication on this filesystem.
                os.link(temporary, target)
                created.append(target)
            finally:
                temporary.unlink(missing_ok=True)
    except Exception:
        for target in created:
            target.unlink()
        raise
    print("Configuration package installed: " + pin["id"] + " " + pin["version"])
    return [configuration / relative for relative in files]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--configuration", type=Path, required=True)
    args = parser.parse_args()
    try:
        pins = sorted(args.pins.glob("*.json"))
        if not pins:
            print("No external configuration packages pinned")
        for path in pins:
            prepare(path, args.cache, args.configuration)
        if pins and os.environ.get("OE_CONFIGURATION_AUTOCREATE", "true").lower() != "true":
            print("Configuration files installed; application import is DISABLED by OE_CONFIGURATION_AUTOCREATE")
    except Exception as error:
        parser.exit(1, "Configuration package preparation failed: " + str(error) + "\n")
