"""Pair an ADB-connected tablet over a loopback-only USB reverse tunnel."""
from pathlib import Path
import json,subprocess,zipfile,uuid,os,shutil
ROOT=Path(__file__).resolve().parents[1]
ADB=Path(os.environ.get('SCREENMATE_ADB') or shutil.which('adb') or 'adb')
HELPER=Path(os.environ.get('SCREENMATE_TABLET_API_HELPER') or Path(__file__).with_name('tablet_api_helper.py'))
def main():
    settings=json.loads((ROOT/'runtime/settings.private.json').read_text(encoding='utf-8'))
    subprocess.run([str(ADB),'reverse','tcp:17860','tcp:17860'],check=True,capture_output=True)
    archive=ROOT/'runtime/tablet-bridge.zip'
    folder=ROOT/'integrations/astrbot_plugin_xiaojing_screenmate'
    with zipfile.ZipFile(archive,'w') as z:
        for p in folder.iterdir():
            if p.is_file() and p.suffix in ('.py','.json','.yaml','.txt'):z.write(p,folder.name+'/'+p.name)
    private=ROOT/'runtime/tablet-pair.private.json'
    private.write_text(json.dumps({'token':settings['token']}),encoding='utf-8')
    for src,dst in [(archive,'bridge.zip'),(private,'bridge-pair.json')]:subprocess.run([str(ADB),'push',str(src),'/data/local/tmp/'+dst],check=True,capture_output=True)
    helper=HELPER.read_text(encoding='utf-8').split('if __name__')[0]
    code=helper+'''
import uuid
pair=json.loads(Path('/data/local/tmp/bridge-pair.json').read_text())
cap=json.loads((BASE/'data/config/astrbot_plugin_fish_capabilities_config.json').read_text())
session=str(cap['bili_private_session']);pieces=session.split(':')
if len(pieces)!=3 or pieces[1]!='FriendMessage' or pieces[2] not in list(map(str,cap['owners'])):raise RuntimeError('owner_session')
cfg={'enabled':True,'base_url':'http://127.0.0.1:17860','token':pair['token'],'owner_id':pieces[2],'owner_session':session,'vision_provider_id':cap.get('bili_vision_provider_id') or cap['bili_provider_id'],'poll_seconds':2,'vision_min_seconds':60,'initiative_enabled':True,'initiative_seconds':900,'bot_id':''}
p=BASE/'data/config/astrbot_plugin_xiaojing_screenmate_config.json'
if p.exists():p.with_name('screenmate-before-'+str(int(time.time()))+'.private.json').write_bytes(p.read_bytes())
p.write_text(json.dumps(cfg),encoding='utf-8');p.chmod(0o600)
boundary='----screenmate'+uuid.uuid4().hex
body=('--'+boundary+'\\r\\nContent-Disposition: form-data; name="file"; filename="bridge.zip"\\r\\nContent-Type: application/zip\\r\\n\\r\\n').encode()+Path('/data/local/tmp/bridge.zip').read_bytes()+('\\r\\n--'+boundary+'--\\r\\n').encode()
h=headers();h['Content-Type']='multipart/form-data; boundary='+boundary
req=urllib.request.Request('http://127.0.0.1:6185/api/plugin/install-upload',data=body,headers=h)
result=json.load(urllib.request.urlopen(req,timeout=60))
if result.get('status')!='ok':raise RuntimeError('bridge_install_failed')
print(json.dumps({'installed':True,'owner_session_reused':True,'public_port_opened':False}))
'''
    try:
        r=subprocess.run([str(ADB),'shell','-T','run-as','com.termux','/data/data/com.termux/files/usr/bin/python','-'],input=code,text=True,encoding='utf-8',capture_output=True,timeout=90)
        print(r.stdout);print(r.stderr[-400:]);r.check_returncode()
    finally:
        private.unlink(missing_ok=True)
        subprocess.run([str(ADB),'shell','rm','-f','/data/local/tmp/bridge-pair.json'],capture_output=True)
if __name__=='__main__':main()
