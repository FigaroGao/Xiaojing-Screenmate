"""Generate fixed presence phrases once using the configured local Feiyu service."""
import sys,json,time,wave,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests
from screenmate.voice_bank import PHRASES

def main():
    root=Path(__file__).resolve().parents[1]/'runtime'
    config=json.loads((root/'settings.private.json').read_text())
    folder=root/'voice-bank';folder.mkdir(exist_ok=True)
    session=requests.Session();session.trust_env=False
    session.headers['Authorization']='Bearer '+config['voice_key']
    def call(method,path,**kwargs):
        r=session.request(method,config['voice_url'].rstrip('/')+path,timeout=25,allow_redirects=False,**kwargs)
        r.raise_for_status();return r
    try:
        for ident,text in PHRASES.items():
            target=folder/(ident+'.wav')
            if target.exists():continue
            job=call('POST','/v1/speech',json={'voice':'feiyu','text':text,'style':config['voice_style']}).json()['id']
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                detail=call('GET',f'/v1/jobs/{job}').json();status=detail['status']
                if status=='success':break
                if status in ('failed','interrupted'):raise RuntimeError('Voice generation failed: '+str(detail.get('error','unknown'))[:300])
                time.sleep(.5)
            else:raise TimeoutError('Voice bank generation timeout')
            audio=call('GET',f'/v1/jobs/{job}/audio').content
            with wave.open(io.BytesIO(audio)) as wav:
                if wav.getcomptype()!='NONE' or wav.getnframes()==0:raise ValueError('Invalid PCM WAV')
            temp=target.with_suffix('.tmp');temp.write_bytes(audio);temp.replace(target)
            print('saved',ident,flush=True)
        (folder/'manifest.json').write_text(json.dumps(PHRASES,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:session.close()

if __name__=='__main__':main()
