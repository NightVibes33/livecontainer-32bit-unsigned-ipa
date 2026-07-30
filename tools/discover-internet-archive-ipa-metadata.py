#!/usr/bin/env python3
"""Discover Internet Archive IPA metadata without downloading copyrighted binaries.

Produces a catalog of candidate items/files for later authorized validation.
"""
from __future__ import annotations
import argparse, json, urllib.parse, urllib.request

ALLOWED_LICENSE_MARKERS = (
    'creativecommons.org/publicdomain',
    'creativecommons.org/licenses/by',
    'creativecommons.org/licenses/zero',
    'public domain',
)


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'LiveContainer-Compat32/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--query', default='mediatype:software AND (title:ipa OR subject:ipa OR description:ipa)')
    ap.add_argument('--rows', type=int, default=100)
    ap.add_argument('--output', default='internet-archive-ipa-catalog.json')
    ap.add_argument('--licensed-only', action='store_true', default=True)
    args = ap.parse_args()

    params = urllib.parse.urlencode({
        'q': args.query,
        'fl[]': ['identifier', 'title', 'creator', 'licenseurl', 'rights', 'description'],
        'rows': min(max(args.rows, 1), 1000),
        'page': 1,
        'output': 'json',
    }, doseq=True)
    search = get_json('https://archive.org/advancedsearch.php?' + params)
    candidates = []
    for doc in search.get('response', {}).get('docs', []):
        ident = doc.get('identifier')
        if not ident:
            continue
        rights_text = ' '.join(str(doc.get(k, '')) for k in ('licenseurl', 'rights', 'description')).lower()
        clearly_permitted = any(marker in rights_text for marker in ALLOWED_LICENSE_MARKERS)
        metadata = get_json('https://archive.org/metadata/' + urllib.parse.quote(ident))
        ipa_files = []
        for f in metadata.get('files', []):
            name = str(f.get('name', ''))
            if name.lower().endswith('.ipa'):
                ipa_files.append({
                    'name': name,
                    'size': f.get('size'),
                    'sha1': f.get('sha1'),
                    'md5': f.get('md5'),
                    'source': f.get('source'),
                })
        if not ipa_files:
            continue
        candidates.append({
            'identifier': ident,
            'title': doc.get('title'),
            'creator': doc.get('creator'),
            'licenseurl': doc.get('licenseurl'),
            'rights': doc.get('rights'),
            'clearlyPermitted': clearly_permitted,
            'ipaFiles': ipa_files,
            'metadataURL': f'https://archive.org/metadata/{ident}',
        })

    if args.licensed_only:
        candidates = [c for c in candidates if c['clearlyPermitted']]
    out = {
        'schemaVersion': 1,
        'query': args.query,
        'metadataOnly': True,
        'binaryDownloadPerformed': False,
        'candidateCount': len(candidates),
        'candidates': candidates,
    }
    with open(args.output, 'w') as f:
        json.dump(out, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
