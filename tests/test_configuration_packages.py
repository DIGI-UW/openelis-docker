"""Package installation uses synthetic archives, without network or an OpenELIS database."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from test_release_manifest import ROOT

spec = importlib.util.spec_from_file_location("packages", ROOT / "scripts/prepare-configuration-packages.py")
packages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packages)


class ConfigurationPackageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.pin = self.root / "pin.json"
        self.cache = self.root / "cache"
        self.configuration = self.root / "configuration"
        self.payload = {"configuration/backend/dictionaries/catalog.csv": b"category,entry\nTest,Example\n",
                        "configuration/backend/roles/roles.csv": b"name\nExample\n",
                        "evidence/NOTICE.txt": b"Synthetic metadata"}
        self.set_package()
        self.fetch = Mock(side_effect=lambda url, path: path.write_bytes(self.content))

    def set_package(self, identity="lab-vocabulary", version="1.0", entries=None):
        entries = entries or self.payload
        manifest = {"format": packages.FORMAT, "packageId": identity, "packageVersion": version,
                    "files": {name: {"sha256": packages.digest(data), "bytes": len(data)}
                              for name, data in entries.items()}}
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
            archive.writestr("manifest.json", json.dumps(manifest))
        self.content = output.getvalue()
        self.pin.write_text(json.dumps({"id": identity, "version": version,
            "url": "https://metadata.example.org/releases/" + identity + "/" + version + "/metadata.zip",
            "sha256": packages.digest(self.content)}))

    def prepare(self, fetch=None):
        return packages.prepare(self.pin, self.cache, self.configuration, fetch or self.fetch)

    def oci_fixture(self):
        layer = {"mediaType": "application/zip", "digest": "sha256:" + packages.digest(self.content),
                 "size": len(self.content)}
        manifest = json.dumps({"schemaVersion": 2, "layers": [layer]}).encode()
        pin = json.loads(self.pin.read_text())
        pin["url"] = "oci://ghcr.io/example/catalog@sha256:" + packages.digest(manifest)
        self.pin.write_text(json.dumps(pin))
        return manifest

    def test_oci_digest_pin_installs_then_restarts_offline(self):
        manifest = self.oci_fixture()
        with patch.object(packages, "registry_bytes", side_effect=[b'{"token":"test-token"}', manifest, self.content]) as request:
            installed = self.prepare(packages.download)
        self.assertEqual(3, request.call_count)
        self.assertIn("/manifests/sha256:", request.call_args_list[1].args[0])
        with patch.object(packages, "registry_bytes", side_effect=AssertionError("Must use verified cache")):
            self.assertEqual(installed, self.prepare(packages.download))

    def test_oci_rejects_changed_manifest_and_changed_layer_before_install(self):
        manifest = self.oci_fixture()
        for responses, message in (
            ([b'{"token":"test-token"}', manifest + b" "], "manifest differs"),
            ([b'{"token":"test-token"}', manifest, b"corrupt"], "layer differs"),
        ):
            with patch.object(packages, "registry_bytes", side_effect=responses):
                with self.assertRaisesRegex(ValueError, message):
                    self.prepare(packages.download)
            self.assertFalse(self.configuration.exists())

    def test_oci_cannot_use_a_tag_or_send_credentials_to_another_registry(self):
        for url in ("oci://ghcr.io/example/catalog:latest", "oci://other.example/a@sha256:" + "a" * 64,
                    "oci://user:password@ghcr.io/a@sha256:" + "a" * 64):
            with self.assertRaisesRegex(ValueError, "OCI package"):
                packages.oci_reference(url)

    def test_registry_authentication_is_not_forwarded_to_blob_redirects(self):
        request = packages.urllib.request.Request("https://ghcr.io/v2/example/blobs/sha256:abc",
                                                 headers={"Authorization": "Bearer example"})
        redirected = packages.HTTPSRedirects().redirect_request(
            request, None, 302, "Found", {}, "https://storage.example/blob")
        self.assertIsNone(redirected.get_header("Authorization"))

    def test_installs_normal_config_files_and_keeps_evidence_outside_scan(self):
        targets = self.prepare()
        self.assertEqual(2, len(targets))
        self.assertEqual(b"category,entry\nTest,Example\n", targets[0].read_bytes())
        self.assertEqual("pkg--lab-vocabulary--1.0--catalog.csv", targets[0].name)
        self.assertFalse((self.configuration / "evidence").exists())
        self.assertEqual(1, len(list(self.cache.glob("*.zip"))))

    def test_restart_reuses_verified_cache_without_network(self):
        targets = self.prepare()
        offline = Mock(side_effect=OSError("offline"))
        self.assertEqual(targets, self.prepare(offline))
        offline.assert_not_called()

    def test_multiple_publishers_and_upgrade_coexist_with_site_files(self):
        site = self.configuration / "backend/dictionaries/site.csv"
        site.parent.mkdir(parents=True)
        site.write_text("Local choices")
        previous = self.prepare()
        self.set_package(version="2.0")
        upgraded = self.prepare()
        self.set_package(identity="other-publisher")
        other = self.prepare()
        self.assertEqual("Local choices", site.read_text())
        self.assertEqual(6, len(set(previous + upgraded + other)))
        self.assertTrue(all(path.exists() for path in previous + upgraded + other))

    def test_edited_managed_file_is_preserved_and_conflict_precedes_any_writes(self):
        targets = self.prepare()
        targets[1].write_text("Local edit")
        targets[0].unlink()
        with self.assertRaisesRegex(ValueError, "conflict"):
            self.prepare()
        self.assertEqual("Local edit", targets[1].read_text())
        self.assertFalse(targets[0].exists())

    def test_wrong_checksum_never_installs_and_retains_prior_version(self):
        previous = self.prepare()
        self.set_package(version="2.0")
        with self.assertRaisesRegex(ValueError, "checksum differs"):
            self.prepare(Mock(side_effect=lambda url, path: path.write_bytes(b"bad")))
        self.assertTrue(all(path.exists() for path in previous))
        self.assertFalse(list(self.cache.glob(".download-*")))
        self.assertEqual(2, len(list(self.configuration.rglob("*.csv"))))

    def test_interruption_cleans_partial_download_and_retry_works(self):
        def interrupted(url, path):
            path.write_bytes(b"partial")
            raise OSError("interrupted")
        with self.assertRaisesRegex(OSError, "interrupted"):
            self.prepare(Mock(side_effect=interrupted))
        self.assertEqual([], list(self.cache.iterdir()))
        self.assertEqual(2, len(self.prepare()))

    def test_failed_publication_removes_only_files_created_in_that_attempt(self):
        real_link = packages.os.link
        calls = []
        def fail_second(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError("disk failure")
            return real_link(source, target)
        with patch.object(packages.os, "link", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "disk failure"):
                self.prepare()
        self.assertFalse(list(self.configuration.rglob("*.csv")))
        self.assertFalse(list(self.configuration.rglob(".package-*")))
        self.assertEqual(2, len(self.prepare()))

    def test_corrupt_cache_is_repaired(self):
        self.prepare()
        cached = next(self.cache.glob("*.zip"))
        cached.write_bytes(b"broken")
        self.prepare()
        self.assertEqual(self.content, cached.read_bytes())
        self.assertEqual(2, self.fetch.call_count)

    def test_manifest_identity_must_match_pin(self):
        pin = json.loads(self.pin.read_text())
        pin["version"] = "different"
        self.pin.write_text(json.dumps(pin))
        with self.assertRaisesRegex(ValueError, "manifest differs"):
            self.prepare()
        self.assertFalse(self.configuration.exists())

    def test_path_traversal_or_unrecognized_install_locations_are_rejected(self):
        for name in ("../escape.csv", "/absolute.csv", "configuration/backend/../escape.csv",
                     "configuration/backend/dictionaries/code.sh", "configuration/backend/dictionaries/a/b.csv"):
            self.set_package(entries={name: b"bad"})
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.prepare()
        self.assertFalse(self.configuration.exists())

    def test_symlink_destination_is_not_followed(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.configuration / "backend").mkdir(parents=True)
        (self.configuration / "backend/dictionaries").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.prepare()
        self.assertEqual([], list(outside.iterdir()))

    def test_duplicate_and_symlink_archive_entries_are_rejected(self):
        for symlink in (False, True):
            output = io.BytesIO(self.content)
            with zipfile.ZipFile(output, "a") as archive:
                if symlink:
                    entry = zipfile.ZipInfo("evidence/link")
                    entry.create_system = 3
                    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(entry, "/outside")
                else:
                    archive.writestr("manifest.json", "{}")
            pin = json.loads(self.pin.read_text())
            with self.subTest(symlink=symlink), self.assertRaises(ValueError):
                packages.configuration_files(output.getvalue(), pin)

    def test_manifest_payload_hashes_are_checked(self):
        pin = json.loads(self.pin.read_text())
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.content)) as source, zipfile.ZipFile(output, "w") as target:
            for name in source.namelist():
                data = source.read(name)
                target.writestr(name, data + b"bad" if name.endswith("catalog.csv") else data)
        with self.assertRaisesRegex(ValueError, "Payload checksum"):
            packages.configuration_files(output.getvalue(), pin)

    def test_https_is_required_for_download_and_redirect(self):
        pin = json.loads(self.pin.read_text())
        pin["url"] = "http://example.org/catalog.zip"
        self.pin.write_text(json.dumps(pin))
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            self.prepare()
        self.fetch.assert_not_called()
        with self.assertRaisesRegex(ValueError, "non-HTTPS"):
            packages.HTTPSRedirects().redirect_request(None, None, 302, "", {}, "http://example.org/catalog.zip")


if __name__ == "__main__":
    unittest.main()
