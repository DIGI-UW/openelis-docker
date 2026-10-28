"""Exercise the actual packaging script without downloading application images.

Docker transfer itself has a separate disconnected-daemon test in CI and packaging.
"""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import secrets
import subprocess
import tarfile
import tempfile
import unittest

import test_release_manifest
from test_release_manifest import ROOT


class OfflinePackageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        fixture = test_release_manifest.ReleaseManifestTest()
        fixture.setUp()
        (self.repo / 'docker-compose.yml').write_text(fixture.render())
        (self.repo / 'deployment-manifest.json').write_text(json.dumps(fixture.manifest))
        shutil.copyfile(ROOT / '.env.example', self.repo / '.env.example')
        (self.repo / 'configs/database').mkdir(parents=True)
        shutil.copyfile(ROOT / 'configs/database/database.env', self.repo / 'configs/database/database.env')
        for directory, names in [('scripts', ['apply-release-manifest.py', 'package-offline.sh']),
                                 ('tests', ['offline-roundtrip.sh'])]:
            (self.repo / directory).mkdir()
            for name in names:
                shutil.copyfile(ROOT / directory / name, self.repo / directory / name)
        (self.repo / '.gitignore').write_text('.env\nsecrets/\n')
        for args in [('init',), ('config', 'user.name', 'Offline Test'),
                     ('config', 'user.email', 'offline@example.invalid'), ('add', '.'),
                     ('commit', '-m', 'Pinned release fixture')]:
            subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)
        # These private installation files must never enter a published package.
        (self.repo / '.env').write_text('PRIVATE_SITE_PASSWORD=' + secrets.token_hex(24) + '\n')
        (self.repo / 'secrets').mkdir()
        (self.repo / 'secrets/key').write_text(secrets.token_hex(24))
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.record = self.root / 'docker-calls.jsonl'
        fake = self.bin / 'docker'
        fake.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
a = sys.argv[1:]
with open(os.environ['DOCKER_RECORD'], 'a') as out: out.write(json.dumps(a) + '\\n')
if a[0] == 'compose': os.execv(os.environ['REAL_DOCKER'], ['docker', *a])
if a[0] == 'info': print('classic' if os.environ.get('CLASSIC') else 'io.containerd.snapshotter.v1')
if a[0] == 'pull' and os.environ.get('MISSING') and '-certs@' in a[-1]: sys.exit(1)
if a[:2] == ['image', 'save']: pathlib.Path(a[a.index('-o') + 1]).write_bytes(b'image-archive-fixture')
if a[0] == 'run': print('test-daemon')
if a[0] == 'exec' and 'create' in a: print('test-container')
if a[0] == 'exec' and 'load' in a: sys.stdin.buffer.read()
''')
        fake.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'REAL_DOCKER': shutil.which('docker'), 'DOCKER_RECORD': str(self.record)}
        self.output = self.root / 'output'

    def package(self):
        return subprocess.run(['bash', 'scripts/package-offline.sh', str(self.output)],
                              cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=45)

    def test_offline_contains_identical_release_and_all_images_without_site_secrets(self):
        result = self.package()
        self.assertEqual(0, result.returncode, result.stderr)
        pieces = sorted(self.output.glob('*.part-*'))
        self.assertTrue(pieces)
        sums = (self.output / 'SHA256SUMS').read_text()
        for part in pieces:
            self.assertIn(hashlib.sha256(part.read_bytes()).hexdigest() + '  ' + part.name, sums)
        archive = gzip.decompress(b''.join(p.read_bytes() for p in pieces))
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            prefix = 'openelis-3.4.0/'
            for name in ['docker-compose.yml', 'deployment-manifest.json', '.env.example']:
                self.assertEqual((self.repo / name).read_bytes(), bundle.extractfile(prefix + name).read())
            self.assertNotIn(prefix + '.env', bundle.getnames())
            self.assertNotIn(prefix + 'secrets/key', bundle.getnames())
            refs = bundle.extractfile(prefix + 'images.txt').read().decode().splitlines()
            self.assertEqual(8, len(refs))  # seven OE2 images plus autoheal; no mock
            self.assertFalse(any('analyzer-mock' in ref for ref in refs))
        calls = [json.loads(line) for line in self.record.read_text().splitlines()]
        self.assertEqual(set(refs), {a[-1] for a in calls if a[:3] == ['pull', '--platform', 'linux/amd64']})
        self.assertEqual(set(refs), {a[-1] for a in calls if a[0] == 'exec' and 'inspect' in a})
        saved = next(a for a in calls if a[:2] == ['image', 'save'])
        self.assertNotIn('--platform', saved)  # must retain the original index digest
        self.assertEqual(8, len(saved[4:]))
        self.assertTrue(all(':offline-' in ref for ref in saved[4:]))
        self.assertTrue(any(a[0] == 'run' and '--network' in a and 'none' in a for a in calls))
        self.assertEqual(8, sum(a[0] == 'exec' and 'start' in a for a in calls))

    def test_missing_image_does_not_produce_a_complete_package(self):
        self.env['MISSING'] = '1'
        self.assertNotEqual(0, self.package().returncode)
        self.assertFalse((self.output / 'SHA256SUMS').exists())
        calls = [json.loads(line) for line in self.record.read_text().splitlines()]
        self.assertTrue(any(a[0] == 'pull' and '-certs@' in a[-1] for a in calls))
        self.assertFalse(any(a[:2] == ['image', 'save'] for a in calls))

    def test_classic_store_fails_before_packaging(self):
        self.env['CLASSIC'] = '1'
        result = self.package()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('containerd image store', result.stderr)
        self.assertFalse(self.output.exists())

    def test_uncommitted_configuration_cannot_diverge_from_archive(self):
        with (self.repo / 'docker-compose.yml').open('a') as out:
            out.write('\n# Unreleased change\n')
        self.assertNotEqual(0, self.package().returncode)
        self.assertFalse(self.record.exists())
