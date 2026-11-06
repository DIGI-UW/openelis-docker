"""Validate operator settings through Docker Compose for template and release."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_release_manifest
from test_release_manifest import ROOT


class InstallConfigurationTest(unittest.TestCase):
    def render(self, pinned=False, **settings):
        fixture = test_release_manifest.ReleaseManifestTest()
        fixture.setUp()
        source = fixture.render() if pinned else fixture.source
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('OE_', 'SSL_', 'COMPOSE_', 'ANALYZER_'))
               and key not in ('TZ', 'ADMIN_PASSWORD', 'POSTGRES_PASSWORD')}
        env.update(OE_DB_PASSWORD='validation', ADMIN_PASSWORD='validation',
                   POSTGRES_PASSWORD='validation', ANALYZER_BRIDGE_PAIRING_CODE='validation')
        if not pinned:
            env['OE_IMAGE_TAG'] = 'develop'
        env.update(settings)
        with tempfile.TemporaryDirectory() as temp:
            compose = Path(temp) / 'compose.yml'
            compose.write_text(source)
            return subprocess.run(
                ['docker', 'compose', '--project-directory', str(ROOT),
                 '--env-file', str(ROOT / '.env.example'), '-f', str(compose),
                 'config', '--format', 'json'], env=env, text=True, capture_output=True)

    def services(self, **settings):
        result = self.render(**settings)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)['services']

    def test_template_and_release_keep_internal_ports_on_loopback(self):
        for pinned in (False, True):
            with self.subTest(pinned=pinned):
                services = self.services(pinned=pinned)
                for service in ('db.openelis.org', 'oe.openelis.org', 'fhir.openelis.org'):
                    self.assertTrue(services[service]['ports'])
                    for port in services[service]['ports']:
                        self.assertEqual('127.0.0.1', port['host_ip'])
                for service, expected in [('proxy', {80, 443}),
                                          ('openelis-analyzer-bridge', {12001, 12011, 2575})]:
                    ports = services[service]['ports']
                    self.assertEqual(expected, {int(p['published']) for p in ports})
                    self.assertTrue(all(p.get('host_ip', '0.0.0.0') == '0.0.0.0' for p in ports))

    def test_site_timezone_and_custom_ports_do_not_remove_isolation(self):
        services = self.services(pinned=True, TZ='Pacific/Port_Moresby',
                                 OE_WEBAPP_HTTP_PORT='18080', OE_WEBAPP_HTTPS_PORT='18443',
                                 OE_FHIR_HTTP_PORT='18081', OE_FHIR_HTTPS_PORT='18444',
                                 ANALYZER_BRIDGE_PAIRING_CODE='explicit-site-code')
        for service in ('oe.openelis.org', 'fhir.openelis.org', 'openelis-analyzer-bridge', 'autoheal'):
            self.assertEqual('Pacific/Port_Moresby', services[service]['environment']['TZ'])
        for service, expected in [('oe.openelis.org', {'18080', '18443'}),
                                  ('fhir.openelis.org', {'18081', '18444'})]:
            self.assertEqual(expected, {p['published'] for p in services[service]['ports']})
            self.assertTrue(all(p['host_ip'] == '127.0.0.1' for p in services[service]['ports']))
        self.assertEqual('explicit-site-code', services['oe.openelis.org']['environment']['ANALYZER_BRIDGE_PAIRING_CODE'])
        self.assertEqual('explicit-site-code', services['openelis-analyzer-bridge']['environment']['BRIDGE_PAIRING_CODE'])

    def test_blank_pairing_code_stops_template_and_release_before_startup(self):
        for pinned in (False, True):
            with self.subTest(pinned=pinned):
                result = self.render(pinned=pinned, ANALYZER_BRIDGE_PAIRING_CODE='')
                self.assertNotEqual(0, result.returncode)
                self.assertIn('Set a private ANALYZER_BRIDGE_PAIRING_CODE', result.stderr)
