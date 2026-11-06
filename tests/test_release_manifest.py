import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manifest', ROOT / 'scripts/apply-release-manifest.py')
manifest_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest_module)


class ReleaseManifestTest(unittest.TestCase):
    def setUp(self):
        self.sha = 'a' * 40
        self.manifest = {'schemaVersion': 1, 'appBranch': '3.4.0', 'appSha': self.sha,
                         'images': {name: 'itechuw/openelis-global-2' + suffix + '@sha256:' + 'b' * 64
                                    for name, suffix in manifest_module.SERVICES.items()}}
        self.source = (ROOT / 'docker-compose.yml').read_text()

    def render(self):
        return manifest_module.render(self.source, self.manifest, '3.4.0', self.sha)

    def test_whole_distribution_uses_one_tested_set_and_retains_comments(self):
        pinned = self.render()
        self.assertNotIn(':develop', pinned)
        self.assertNotIn('OE_IMAGE_TAG', pinned)
        self.assertIn('# The OE2 image packages', pinned)
        for name, reference in self.manifest['images'].items():
            if name != 'astm-simulator':
                self.assertIn(reference, pinned)
        self.assertEqual(2, pinned.count(self.manifest['images']['openelis-analyzer-bridge']))
        self.assertEqual(pinned, manifest_module.render(pinned, self.manifest, '3.4.0', self.sha))

    def test_rejects_mixed_release_missing_images_and_wrong_repository(self):
        changes = [('appSha', 'c' * 40), ('appBranch', '3.3.0'), ('schemaVersion', 2), ('images', {})]
        for key, value in changes:
            with self.subTest(key=key):
                old = self.manifest[key]
                self.manifest[key] = value
                with self.assertRaises(ValueError): self.render()
                self.manifest[key] = old
        self.manifest['images']['certs'] = 'itechuw/certgen@sha256:' + 'b' * 64
        with self.assertRaises(ValueError): self.render()

    def test_rejects_unrecognized_service_before_writing(self):
        self.source = self.source.replace('    proxy:', '    unexpected:')
        with self.assertRaises(ValueError): self.render()

    def test_rejects_duplicate_json_fields(self):
        with self.assertRaises(ValueError):
            json.loads('{"schemaVersion":1,"schemaVersion":2}', object_pairs_hook=manifest_module.unique_object)

    def test_command_writes_and_verifies_pins_without_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            compose = folder / 'compose.yml'
            compose.write_text(self.source)
            manifest = folder / 'manifest.json'
            manifest.write_text(json.dumps(self.manifest))
            command = ['python3', str(ROOT / 'scripts/apply-release-manifest.py'), str(manifest),
                       '3.4.0', self.sha, '--compose', str(compose)]
            subprocess.run(command, check=True, capture_output=True)
            subprocess.run(command + ['--check'], check=True, capture_output=True)
            compose.write_text(compose.read_text().replace('b' * 64, 'c' * 64, 1))
            self.assertNotEqual(0, subprocess.run(command + ['--check'], capture_output=True).returncode)


if __name__ == '__main__': unittest.main()
