"""Executed on the tablet by maintenance tools; never sends dashboard secrets to PC."""
import json,time,base64,hmac,hashlib,urllib.request
from pathlib import Path
BASE=Path('/data/data/com.termux/files/home/AstrBot')

def headers():
    dashboard=json.loads((BASE/'data/cmd_config.json').read_text(encoding='utf-8-sig'))['dashboard']
    enc=lambda data:base64.urlsafe_b64encode(data).rstrip(b'=')
    message=enc(b'{"alg":"HS256","typ":"JWT"}')+b'.'+enc(json.dumps({'username':dashboard['username'],'exp':int(time.time())+600}).encode())
    token=(message+b'.'+enc(hmac.new(dashboard['jwt_secret'].encode(),message,hashlib.sha256).digest())).decode()
    return {'Authorization':'Bearer '+token,'Content-Type':'application/json'}

def call(path,data=None,method=None,timeout=90):
    request=urllib.request.Request('http://127.0.0.1:6185'+path,data=json.dumps(data).encode() if data is not None else None,
                                   headers=headers(),method=method)
    return json.load(urllib.request.urlopen(request,timeout=timeout))
