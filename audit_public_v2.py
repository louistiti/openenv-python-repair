"""Read-only audit of public v2 release, image manifest, and dataset viewer."""
import hashlib
import json
import pathlib
import re
import time
from urllib.parse import urlparse

import requests

ROOT = pathlib.Path(__file__).parent
SESSION = requests.Session()
SESSION.headers['Accept'] = 'application/vnd.github+json'


def get(url, **kwargs):
    response = SESSION.get(url, timeout=120, **kwargs)
    response.raise_for_status()
    return response


def main():
    release = get('https://api.github.com/repos/louistiti/openenv-python-repair/releases/tags/v2').json()
    assets = {a['name']: a['browser_download_url'] for a in release['assets']}
    names = ['image-digest-v2.txt', 'public-image-digest-v2.txt', 'test-image-v2.txt',
             'replay-image-v2.json', 'replay-public-v2.json', 'validation-image-v2.json',
             'validation-public-v2.json', 'image-inspect-v2.json',
             'image-public-inspect-v2.json', 'schema-image-v2.json', 'schema-public-v2.json']
    for name in names:
        data = get(assets[name]).content
        (ROOT / name).write_bytes(data)
    image = (ROOT / 'image-digest-v2.txt').read_text().strip()
    assert image == (ROOT / 'public-image-digest-v2.txt').read_text().strip()
    assert image.startswith('ghcr.io/louistiti/openenv-python-repair@sha256:')
    tasks = json.loads((ROOT / 'tasks.json').read_text())
    expected_ids = {t['task_id'] for t in tasks}
    cases = sum(len(t['cases']) for t in tasks)
    for name in ['replay-image-v2.json', 'replay-public-v2.json']:
        report = json.loads((ROOT / name).read_text())
        assert all(report[k] is True for k in ['health', 'schema', 'state', 'http_terminal'])
        rows = report['tasks']
        assert len(rows) == 1200 and {r['task_id'] for r in rows} == expected_ids
        assert sum(r['cases'] for r in rows) == cases == 151780
        assert all(r['oracle_reward'] == 1 and r['starter_reward'] < 1 and r['reset_verified'] for r in rows)
    request = json.loads((ROOT / 'submission-v2.json').read_text())
    for name in ['schema-image-v2.json', 'schema-public-v2.json']:
        assert json.loads((ROOT / name).read_text()) == request['schema']
    for name in ['validation-image-v2.json', 'validation-public-v2.json']:
        validation = json.loads((ROOT / name).read_text())
        assert validation['passed'] and validation['summary']['passed_count'] == 6
    assert '1214 passed' in (ROOT / 'test-image-v2.txt').read_text()

    registry = 'https://ghcr.io/v2/louistiti/openenv-python-repair'
    accept = {'Accept': 'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'}
    response = requests.get(registry + '/manifests/v2', headers=accept, timeout=30)
    if response.status_code == 401:
        challenge = dict(re.findall(r'(\w+)="([^"]+)"', response.headers['WWW-Authenticate']))
        assert urlparse(challenge['realm']).netloc == 'ghcr.io'
        token_response = requests.get(challenge['realm'], params={k: challenge[k] for k in ['service', 'scope']}, timeout=30)
        token_response.raise_for_status()
        token = token_response.json().get('token') or token_response.json()['access_token']
        accept['Authorization'] = 'Bearer ' + token
        response = requests.get(registry + '/manifests/v2', headers=accept, timeout=30)
    response.raise_for_status()
    manifest = response.json()
    assert response.headers['Docker-Content-Digest'] == image.split('@')[1]
    assert hashlib.sha256(response.content).hexdigest() == image.split('sha256:')[1]
    assert len(manifest['layers']) <= 128
    compressed = sum(layer['size'] for layer in manifest['layers'])
    assert compressed <= 2 * 1024**3
    config = requests.get(registry + '/blobs/' + manifest['config']['digest'], headers=accept, timeout=60)
    config.raise_for_status()
    config = config.json()
    assert config['os'] == 'linux' and config['architecture'] == 'amd64'
    assert config['config']['Cmd']
    assert config['config']['User'] not in ('', '0', 'root')
    (ROOT / 'manifest-public-v2.json').write_text(json.dumps(manifest, indent=2) + '\n')

    repo = 'Louistiti/openenv-python-repair'
    meta = get('https://huggingface.co/api/datasets/' + repo).json()
    for name in ['tasks.json', 'tasks.jsonl', 'viewer_train.jsonl']:
        data = get('https://huggingface.co/datasets/' + repo + '/resolve/' + meta['sha'] + '/' + name).content
        assert data == (ROOT / name).read_bytes(), name
    for attempt in range(20):
        size = get('https://datasets-server.huggingface.co/size', params={'dataset': repo}).json()
        assert not size.get('failed'), size['failed']
        if size['size']['dataset']['num_rows'] == 1200 and not size.get('pending'):
            break
        if attempt == 0:
            print('Image audit passed; full viewer size conversion still pending.', flush=True)
        time.sleep(15)
    else:
        raise RuntimeError('Full viewer conversion did not finish within five minutes')
    first_rows = get('https://datasets-server.huggingface.co/first-rows', params={'dataset': repo, 'config': 'default', 'split': 'train'}).json()
    canonical = {t['task_id']: t for t in tasks}
    viewer_cases_checked = 0
    for entry in first_rows['rows']:
        row = entry['row']
        assert row['task_id'] in expected_ids
        assert row['num_cases'] == len(canonical[row['task_id']]['cases'])
        # The API may truncate large cells. Full public bytes were checked above.
        if 'cases_json' not in entry.get('truncated_cells', []):
            assert json.loads(row['cases_json']) == canonical[row['task_id']]['cases']
            viewer_cases_checked += 1
    output = {'image': image, 'platform': 'linux/amd64', 'compressed_layer_bytes': compressed,
              'layers': len(manifest['layers']), 'episodes': 1200, 'cases': cases,
              'unit_tests': 1214, 'runtime_checks': 6, 'anonymous_image_replay_verified': True,
              'dataset_commit': meta['sha'], 'dataset_rows': 1200,
              'viewer_sample_rows_verified': len(first_rows['rows']),
              'viewer_sample_case_lists_verified': viewer_cases_checked,
              'canonical_and_viewer_public_bytes_equal': True,
              'release': release['html_url']}
    (ROOT / 'public-verification-v2.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
