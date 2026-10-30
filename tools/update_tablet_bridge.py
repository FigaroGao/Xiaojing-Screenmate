"""Local maintenance: update only the installed Screenmate bridge, with rollback."""
import importlib.util
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pair', ROOT / 'tools/connect_tablet.py')
pair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pair)

def main():
    source = ROOT / 'integrations/astrbot_plugin_xiaojing_screenmate'
    archive=ROOT/'runtime/screenmate-update.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for p in source.glob('*.py'):
            compile(p.read_text(encoding='utf-8'),str(p),'exec');z.write(p,p.name)
    subprocess.run([str(pair.ADB), 'reverse', 'tcp:17860', 'tcp:17860'], check=True, capture_output=True)
    subprocess.run([str(pair.ADB), 'push', str(archive), '/data/local/tmp/screenmate-update.zip'], check=True, capture_output=True)
    helper = pair.HELPER.read_text(encoding='utf-8').split('if __name__')[0]
    code = helper + '''
import zipfile
p=BASE/'data/plugins/astrbot_plugin_xiaojing_screenmate'
files={n:(p/n).read_bytes() if (p/n).exists() else None for n in zipfile.ZipFile('/data/local/tmp/screenmate-update.zip').namelist()}
backup=p/('before-'+str(int(time.time()))+'.zip')
with zipfile.ZipFile(backup,'w') as z:
 for n,data in files.items():
  if data is not None:z.writestr(n,data)
try:
 with zipfile.ZipFile('/data/local/tmp/screenmate-update.zip') as z:
  for n in z.namelist():compile(z.read(n),n,'exec')
  for n in z.namelist():(p/n).write_bytes(z.read(n))
 if call('/api/plugin/reload',{'name':'astrbot_plugin_xiaojing_screenmate'}).get('status')!='ok':raise RuntimeError('reload_failed')
 print(json.dumps({'bridge_updated':True,'napcat_restarted':False}))
except Exception:
 for n,data in files.items():
  if data is None:(p/n).unlink(missing_ok=True)
  else:(p/n).write_bytes(data)
 call('/api/plugin/reload',{'name':'astrbot_plugin_xiaojing_screenmate'});raise
'''
    result = subprocess.run([str(pair.ADB), 'shell', '-T', 'run-as', 'com.termux', '/data/data/com.termux/files/usr/bin/python', '-'], input=code, text=True, encoding='utf-8', capture_output=True, timeout=100)
    print(result.stdout)
    if result.returncode: raise RuntimeError('Tablet update failed; inspect local maintenance logs')

if __name__ == '__main__': main()
