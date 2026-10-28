#!/usr/bin/env python3
"""Pin the distribution to the image set tested and released by OE2 (packaging only)."""
import argparse
import json
from pathlib import Path
import re

SERVICES = {
    "oe.openelis.org": "", "db.openelis.org": "-database",
    "fhir.openelis.org": "-fhir", "frontend.openelis.org": "-frontend",
    "proxy": "-proxy", "certs": "-certs", "openelis-analyzer-bridge": "-analyzer-bridge",
    "astm-simulator": "-analyzer-mock",
}
# autoheal is distribution tooling, not an OE2 build output.
AUTOHEAL = "willfarrell/autoheal:1.2.0@sha256:31f580ef0279eaced5b38d631b08c474d70d8403c1c2fdd6ddcf2e879d5f3f7c"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest field: " + key)
        result[key] = value
    return result


def render(source, manifest, version, commit):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?", version):
        raise ValueError("Select a stable OE2 release")
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Expected the release tag's commit")
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
        raise ValueError("Unsupported release manifest")
    if manifest.get("appBranch") != version or manifest.get("appSha") != commit:
        raise ValueError("Manifest does not match the selected release and commit")
    images = manifest.get("images")
    if not isinstance(images, dict) or set(images) != set(SERVICES):
        raise ValueError("Manifest must contain the complete tested image set")
    for service, suffix in SERVICES.items():
        if not isinstance(images[service], str) or not re.fullmatch(
                r"itechuw/openelis-global-2" + re.escape(suffix) + r"@sha256:[a-f0-9]{64}", images[service]):
            raise ValueError("Invalid released image for " + service)
    expected = {key: value for key, value in images.items() if key != "astm-simulator"}
    expected["analyzer-imports-owner"] = images["openelis-analyzer-bridge"]
    expected["autoheal"] = AUTOHEAL
    # Keep operator-facing comments and layout; replace only image scalar lines
    # in this repository's four-space-indented service definitions.
    current = None
    seen = set()
    result = []
    in_services = False
    for line in source.splitlines(keepends=True):
        if line == "services:\n":
            in_services = True
        elif line and not line[0].isspace() and not line.startswith("#"):
            in_services = False
        match = re.fullmatch(r"    ([a-zA-Z0-9_.-]+):\s*\n", line)
        if in_services and match:
            current = match[1]
        if in_services and re.match(r"        image:", line):
            if current not in expected or current in seen:
                raise ValueError("Unexpected or duplicate image service: " + str(current))
            seen.add(current)
            line = "        image: " + expected[current] + "\n"
        result.append(line)
    if seen != set(expected):
        raise ValueError("Distribution does not contain the expected service images")
    return "".join(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("version")
    parser.add_argument("commit")
    parser.add_argument("--compose", type=Path, default=Path("docker-compose.yml"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(), object_pairs_hook=unique_object)
    source = args.compose.read_text()
    pinned = render(source, manifest, args.version, args.commit)
    if args.check:
        if pinned != source:
            raise ValueError("Compose images differ from the released manifest")
    else:
        temporary = args.compose.with_suffix(".tmp")
        temporary.write_text(pinned)
        temporary.replace(args.compose)


if __name__ == "__main__":
    main()
