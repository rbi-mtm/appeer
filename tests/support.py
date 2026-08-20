"""Shared helpers for verified publication fixture records."""

import json
from pathlib import Path


FIXTURES = Path(__file__).parent / 'fixtures'


def fixture_record(name):
    """Return complete metadata and provenance for a verified fixture."""

    manifest = json.loads(
        (FIXTURES / 'manifest.json').read_text(encoding='utf-8'))
    fixture = manifest[name]
    return fixture['expected'].copy() | {
        'raw_sha256': fixture['sha256'],
        'parser': fixture['expected_parser'],
        'package_version': '0.0.1',
        'git_revision': None,
        'parsed_at': fixture['retrieved_at'],
        'warnings': [],
    }
