"""Execute the actual tagging step against a disposable local Git remote."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import yaml
import test_release_manifest
from test_release_manifest import ROOT


class ReleaseWorkflowTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('docker'), 'Docker Compose required')
    def test_publish_retry_and_changed_manifest_never_move_existing_tag(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/release-distribution.yml').read_text())
        script = next(s['run'] for s in workflow['jobs']['release']['steps']
                      if s.get('name') == 'Prepare or verify the immutable distribution tag')
        fixture = test_release_manifest.ReleaseManifestTest()
        fixture.setUp()
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            repo = temp / 'repo'
            repo.mkdir()
            remote = temp / 'remote.git'
            runtime = temp / 'runtime'
            (runtime / 'oe-release').mkdir(parents=True)
            for name in ('scripts', 'configs'):
                shutil.copytree(ROOT / name, repo / name)
            for name in ('docker-compose.yml', '.env.example'):
                shutil.copyfile(ROOT / name, repo / name)
            shutil.copyfile(ROOT / 'scripts/apply-release-manifest.py', runtime / 'apply-release-manifest.py')
            manifest = runtime / 'oe-release/deployment-manifest.json'
            manifest.write_text(json.dumps(fixture.manifest))
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
            git('init', '-b', 'main')
            git('config', 'user.name', 'Release Test')
            git('config', 'user.email', 'release-test@example.invalid')
            git('add', '.')
            git('commit', '-m', 'Test template')
            git('remote', 'add', 'origin', str(remote))
            env = {**os.environ, 'VERSION': '3.4.0', 'OE_RELEASE_COMMIT': fixture.sha, 'RUNNER_TEMP': str(runtime)}
            env.pop('OE_IMAGE_TAG', None)
            def publish():
                return subprocess.run(['bash', '-ec', script], cwd=repo, env=env, text=True, capture_output=True, timeout=45)
            first = publish()
            self.assertEqual(0, first.returncode, first.stderr)
            before = git('rev-parse', 'refs/tags/3.4.0')
            self.assertNotIn(':develop', (repo / 'docker-compose.yml').read_text())
            self.assertEqual(0, publish().returncode)
            self.assertEqual(before, git('rev-parse', 'refs/tags/3.4.0'))
            fixture.manifest['images']['certs'] = fixture.manifest['images']['certs'].replace('b' * 64, 'c' * 64)
            manifest.write_text(json.dumps(fixture.manifest))
            self.assertNotEqual(0, publish().returncode)
            self.assertEqual(before, git('rev-parse', 'refs/tags/3.4.0'))
            self.assertEqual(before, git('ls-remote', 'origin', 'refs/tags/3.4.0').split()[0])

    def test_default_template_requires_an_explicit_choice(self):
        env = {**os.environ, 'OE_DB_PASSWORD': 'validation', 'ADMIN_PASSWORD': 'validation', 'POSTGRES_PASSWORD': 'validation', 'ANALYZER_BRIDGE_PAIRING_CODE': 'validation'}
        env.pop('OE_IMAGE_TAG', None)
        result = subprocess.run(['docker', 'compose', '--env-file', '.env.example', 'config', '--quiet'],
                                cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Use a distro release', result.stderr)
