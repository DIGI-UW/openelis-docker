#!/usr/bin/env python3
"""Deploy a tested image manifest, verify readiness, and retain diagnostics."""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import urllib.request


SERVICES = {
    "oe.openelis.org": "itechuw/openelis-global-2",
    "db.openelis.org": "itechuw/openelis-global-2-database",
    "fhir.openelis.org": "itechuw/openelis-global-2-fhir",
    "frontend.openelis.org": "itechuw/openelis-global-2-frontend",
    "proxy": "itechuw/openelis-global-2-proxy",
}


def validate_manifest(manifest):
    if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("appSha", "")):
        raise ValueError("Manifest must identify the tested application commit")
    if manifest.get("appBranch") != "develop":
        raise ValueError("Testing deploys require a develop image manifest")
    if set(manifest.get("images", {})) != set(SERVICES):
        raise ValueError("Manifest must include exactly the five application images")
    for service, repository in SERVICES.items():
        if not re.fullmatch(re.escape(repository) + r"@sha256:[0-9a-f]{64}", manifest["images"][service]):
            raise ValueError(f"{service} must use a published DockerHub image digest")
    return manifest


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o644)
    temporary.replace(path)


def run(args, cwd, capture=False):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def verify_review():
    def fetch(path, limit):
        request = urllib.request.Request("https://grist.openelis-global.org" + path,
                                         headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError("Review response exceeds the expected size")
        return body
    identity = json.loads(fetch("/__review/tooling.json", 8192))
    if not re.fullmatch(r"[0-9a-f]{40}", identity.get("harnessSha", "")):
        raise ValueError("Review tooling must identify its verified commit")
    widget = fetch("/oe-review-widget.js", 1048576)
    if hashlib.sha256(widget).hexdigest() != identity.get("widgetSha256"):
        raise ValueError("Hosted widget differs from the verified Review identity")
    checklist = json.loads(fetch("/uat/testing.json", 1048576))
    if not any(section.get("steps") for section in checklist.get("sections", [])):
        raise ValueError("The dedicated testing checklist must be published before enabling Review")
    return identity


def deploy(request, diagnostics):
    manifest = validate_manifest(request["manifest"])
    spec = importlib.util.spec_from_file_location("readiness", pathlib.Path(__file__).with_name("check-readiness.py"))
    readiness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(readiness)
    contract = request["readiness"]
    readiness.validate_contract(**contract)
    app_dir = pathlib.Path(request["deploy_path"]).resolve()
    infra_sha = request["infra_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", infra_sha):
        raise ValueError("Infrastructure must be pinned to an exact commit")
    if not (app_dir / ".env").is_file():
        raise ValueError("An existing server .env is required; configure it before deployment")
    review_identity = verify_review() if request.get("enable_review", False) else None
    # This checkout contains server-owned logs and local credentials. Fast-forward
    # only; a conflict is an actionable failure, never permission to discard them.
    run(["git", "fetch", "origin", "main"], app_dir)
    run(["git", "merge-base", "--is-ancestor", infra_sha, "origin/main"], app_dir)
    run(["git", "merge", "--ff-only", infra_sha], app_dir)
    if run(["git", "rev-parse", "HEAD"], app_dir, True).strip() != infra_sha:
        raise ValueError("Server infrastructure differs from the requested commit")

    review = app_dir / "configs/testing-review"
    review.mkdir(parents=True, exist_ok=True)
    override = review / "deployment-images.json"
    write_json(override, {"services": {name: {"image": image}
                                    for name, image in manifest["images"].items()}})
    compose = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.testing.yml"]
    if review_identity:
        compose += ["-f", "docker-compose.testing-review.yml"]
    compose += ["-f", str(override)]
    try:
        run(compose + ["pull", *SERVICES], app_dir)
        run(compose + ["up", "-d"], app_dir)
        images = {}
        for service, reference in manifest["images"].items():
            container = run(compose + ["ps", "-q", service], app_dir, True).strip()
            if not container or "\n" in container:
                raise ValueError(f"Expected one running container for {service}")
            actual = json.loads(run(["docker", "inspect", container], app_dir, True))[0]
            expected = json.loads(run(["docker", "image", "inspect", reference], app_dir, True))[0]
            if not actual["State"]["Running"] or actual["Image"] != expected["Id"]:
                raise ValueError(f"Running {service} does not match the published image")
            images[service] = {"reference": reference, "imageId": actual["Image"]}
        report = readiness.wait_until_ready(**contract)
        write_json(diagnostics / "readiness.json", report)
        if not report["ready"]:
            raise RuntimeError("Application did not become ready; see deployment diagnostics")
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        target = {"instance": "testing", "state": "ready", "appRepo": "https://github.com/DIGI-UW/OpenELIS-Global-2",
                  "appSha": manifest["appSha"], "appBranch": manifest["appBranch"], "infraSha": infra_sha,
                  "deploymentId": f"testing-{manifest['appSha'][:12]}-{request['run_id']}", "deployedAt": timestamp,
                  "images": images, "verification": {"readiness": report, "url": contract["url"]}}
        if review_identity:
            target["harnessSha"] = review_identity["harnessSha"]
            target["reviewTooling"] = review_identity
        write_json(review / "target.json", target)
        write_json(diagnostics / "target.json", target)
        print(f"Testing is ready at {manifest['appSha']}", flush=True)
    finally:
        for filename, args in [("compose-status.txt", ["ps", "--all"]),
                               ("service-logs.txt", ["logs", "--no-color", "--tail", "250", "oe.openelis.org", "proxy"])]:
            with (diagnostics / filename).open("w", encoding="utf-8") as output:
                subprocess.run(compose + args, cwd=app_dir, stdout=output, stderr=subprocess.STDOUT, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=pathlib.Path)
    args = parser.parse_args()
    diagnostics = args.request.resolve().parent / "diagnostics"
    diagnostics.mkdir(exist_ok=True)
    request = json.loads(args.request.read_text(encoding="utf-8"))
    # Serialize manual and CI deployments on the host as well as in Actions.
    with open("/tmp/openelis-testing-deploy.lock", "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            deploy(request, diagnostics)
        except Exception as error:
            (diagnostics / "failure.txt").write_text(str(error) + "\n", encoding="utf-8")
            print(f"Deployment failed: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
