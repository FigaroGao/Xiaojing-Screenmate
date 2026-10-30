"""Download the public Feiyu TTS release, resume partials, verify published hashes."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "runtime/feiyu-voice/server/models/FeiyuVoice-CosyVoice3"
REPOSITORY = "Esmerubphire/FeiyuVoice-CosyVoice3"


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024**2), b''):
            h.update(block)
    return h.hexdigest()


def download(record, revision):
    relative = record['path']
    path = (DESTINATION / relative).resolve()
    if not path.is_relative_to(DESTINATION.resolve()):
        raise ValueError("Remote path escapes model directory")
    expected = record.get('lfs', {}).get('oid')
    if path.exists() and path.stat().st_size == record['size'] and (not expected or digest(path)==expected):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name+'.part')
    for attempt in range(4):
        try:
            offset = part.stat().st_size if part.exists() else 0
            headers = {'Range':f'bytes={offset}-'} if offset else {}
            url = f'https://huggingface.co/{REPOSITORY}/resolve/{revision}/{relative}'
            with requests.get(url, headers=headers, stream=True, timeout=(30,90)) as response:
                response.raise_for_status()
                append = offset and response.status_code==206
                with part.open('ab' if append else 'wb') as stream:
                    for chunk in response.iter_content(1024**2):
                        stream.write(chunk)
            if part.stat().st_size != record['size']:
                raise ValueError('Size mismatch: '+relative)
            if expected and digest(part)!=expected:
                raise ValueError('SHA256 mismatch: '+relative)
            part.replace(path)
            print('Downloaded:', relative, record['size'], flush=True)
            return
        except Exception:
            if attempt==3:
                raise
            time.sleep(2*(attempt+1))


def main():
    info = requests.get(f'https://huggingface.co/api/models/{REPOSITORY}',timeout=30)
    info.raise_for_status()
    revision = info.json()['sha']
    tree = requests.get(f'https://huggingface.co/api/models/{REPOSITORY}/tree/{revision}?recursive=true',timeout=30)
    tree.raise_for_status()
    files = [r for r in tree.json() if r['type']=='file']
    print('Pinned model revision:',revision,'bytes:',sum(r['size'] for r in files),flush=True)
    DESTINATION.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda record:download(record,revision),files))
    manifest = json.loads((DESTINATION/'files_sha256.json').read_text(encoding='utf-8-sig'))
    for name,record in manifest.items():
        path = (DESTINATION/name).resolve()
        if not path.is_relative_to(DESTINATION.resolve()) or digest(path)!=record['sha256']:
            raise ValueError('Published package integrity check failed: '+name)
    (DESTINATION.parent/'download.private.json').write_text(json.dumps({'repository':REPOSITORY,'revision':revision,'verified':True}),encoding='utf-8')
    print('All published TTS package hashes verified.',flush=True)


if __name__=='__main__':
    main()
