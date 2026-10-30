"""Private loopback Feiyu API: one CUDA model and reference cache per process."""
import hmac
import io
import json
import os
from pathlib import Path
import queue
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'runtime/feiyu-voice/server'
PACKAGE = SERVER / 'models/FeiyuVoice-CosyVoice3'
sys.path.insert(0, str(SERVER))


def fingerprint(paths):
    return [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in paths]


class Resident:
    def __init__(self):
        self.ready = False
        self.error = ''
        self.jobs = {}
        self.lock = threading.RLock()
        self.pending = queue.Queue(maxsize=4)
        self.boot = time.monotonic()
        self.precision = os.environ.get('SCREENMATE_VOICE_PRECISION', 'fp32')
        if self.precision not in ('fp32', 'fp16'):
            raise ValueError('Unsupported resident precision')
        self.memory = {}
        self.dtypes = {}
        self.key = (SERVER / '.runtime/voice-service/api_key.txt').read_text().strip()

    def work(self):
        try:
            self.initialize()
        except Exception as exc:
            self.error = type(exc).__name__ + ': ' + str(exc)
            print(self.error, flush=True)
            return
        while True:
            job_id, text = self.pending.get()
            started = time.monotonic()
            with self.lock:
                self.jobs[job_id]['status'] = 'running'
            try:
                if fingerprint(self.paths) != self.stamp:
                    raise RuntimeError('Verified model or runtime changed; restart service')
                import numpy as np
                import soundfile as sf
                import torch
                from cosyvoice.utils.common import set_all_random_seed
                set_all_random_seed(self.params['seed'])
                with torch.inference_mode():
                    chunks = [x['tts_speech'].detach().cpu().numpy()[0] for x in
                              self.voice.inference_zero_shot(text, '', '', zero_shot_spk_id='screenmate-cute',
                                  stream=False, speed=self.params['speed'], text_frontend=True)]
                audio = np.concatenate(chunks)
                if len(audio) <= 2400 or not np.isfinite(audio).all() or abs(audio).max() <= 1e-4:
                    raise ValueError('Invalid synthesized audio')
                audio *= min(1., .98 / float(abs(audio).max()))
                output = io.BytesIO()
                sf.write(output, audio, self.voice.sample_rate, format='WAV', subtype='PCM_16')
                torch.cuda.synchronize()
                self.memory = {'allocated_mib':round(torch.cuda.memory_allocated()/2**20),
                               'reserved_mib':round(torch.cuda.memory_reserved()/2**20)}
                with self.lock:
                    self.jobs[job_id].update(status='success', wav=output.getvalue(),
                        audio={'seconds':len(audio)/self.voice.sample_rate, 'sample_rate':self.voice.sample_rate,
                               'elapsed_seconds':time.monotonic()-started, 'resident':True, 'style':'cute',
                               'precision':self.precision,'cuda_memory':dict(self.memory)})
            except Exception as exc:
                with self.lock:
                    self.jobs[job_id].update(status='failed', error=type(exc).__name__+': '+str(exc)[:300])
            finally:
                self.pending.task_done()

    def initialize(self):
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='4')
        from feiyu_runtime.common import (load, verify_package, verify_repo, apply_backend_env,
                                         prepare, verify_audio_library, cpu_onnx_sessions)
        profile_path = ROOT / 'runtime/voice-linux/tts/runtime.local.json'
        profile = load(profile_path)
        manifest = verify_package(PACKAGE)
        repo = verify_repo(profile)
        apply_backend_env(profile)
        os.chdir(repo)
        sys.path[:0] = [str(repo),str(repo/'third_party/Matcha-TTS')]
        import torch
        import onnxruntime as ort
        from cosyvoice.cli.cosyvoice import AutoModel
        self.runtime = prepare(torch, profile)
        verify_audio_library(profile)
        selected = manifest['styles']['cute']
        with cpu_onnx_sessions(ort, []):
            self.voice = AutoModel(model_dir=str(PACKAGE/manifest['base_model_dir']),
                                   fp16=self.precision=='fp16', load_trt=False, load_vllm=False)
        checkpoint = PACKAGE / selected['llm_checkpoint']
        weights = torch.load(checkpoint, map_location='cpu', weights_only=True)
        self.voice.model.llm.load_state_dict(weights, strict=True)
        del weights
        if self.precision == 'fp16':
            # Keep the final waveform decoder FP32, as in upstream token2wav.
            self.voice.model.llm.half()
            self.voice.model.flow.half()
            torch.cuda.empty_cache()
        self.runtime = {**self.runtime,'resident_precision':self.precision}
        self.voice.model.llm.eval()
        self.dtypes = {name:str(next(getattr(self.voice.model,name).parameters()).dtype)
                       for name in ('llm','flow','hift')}
        for name in ('llm','flow','hift'):
            if next(getattr(self.voice.model,name).parameters()).device.type != 'cuda':
                raise RuntimeError('Resident model must use CUDA')
        self.params = manifest['inference']
        with torch.inference_mode():
            self.voice.add_zero_shot_spk(self.params['prompt_prefix'] + selected['reference_text'],
                                        str(PACKAGE/selected['reference_audio']), 'screenmate-cute')
        self.paths = [PACKAGE/p for p in load(PACKAGE/'files_sha256.json')]
        self.paths += [repo/p for p in profile['source_sha256']]
        self.paths += [profile_path,PACKAGE/'manifest.json',PACKAGE/'files_sha256.json']
        self.stamp = fingerprint(self.paths)
        torch.cuda.synchronize()
        self.memory = {'allocated_mib':round(torch.cuda.memory_allocated()/2**20),
                       'reserved_mib':round(torch.cuda.memory_reserved()/2**20)}
        self.ready = True
        print('Resident cute model ready in %.1fs' % (time.monotonic()-self.boot), flush=True)


def handler(resident):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, value, binary=False):
            body = value if binary else json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type','audio/wav' if binary else 'application/json')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            return hmac.compare_digest(self.headers.get('Authorization','').encode(),
                                       ('Bearer '+resident.key).encode())

        def do_GET(self):
            if not self.authorized():
                return self.send(401,{'error':'unauthorized'})
            if self.path == '/v1/capabilities':
                return self.send(200,{'tts':[{'voice':'feiyu','available':resident.ready,
                    'styles':['cute']}], 'resident':True, 'loading':not resident.ready and not resident.error,
                    'error':resident.error, 'pid':os.getpid(), 'precision':resident.precision,
                    'cuda_memory':dict(resident.memory), 'parameter_dtypes':dict(resident.dtypes)})
            parts = self.path.split('/')
            with resident.lock:
                job = resident.jobs.get(parts[3]) if len(parts)>=4 and parts[1:3]==['v1','jobs'] else None
                if job and len(parts)==5 and parts[4]=='audio' and job['status']=='success':
                    return self.send(200,job['wav'],True)
                if job and len(parts)==4:
                    return self.send(200,{k:v for k,v in job.items() if k!='wav'})
            self.send(404,{'error':'not_found'})

        def do_POST(self):
            if not self.authorized():
                return self.send(401,{'error':'unauthorized'})
            if self.path!='/v1/speech':
                return self.send(404,{'error':'not_found'})
            if not resident.ready:
                return self.send(503,{'error':'model_initializing' if not resident.error else 'model_failed'})
            try:
                size = int(self.headers.get('Content-Length','0'))
                if not 0<size<=12000:
                    raise ValueError()
                data = json.loads(self.rfile.read(size))
                text = data['text']
                if not isinstance(text,str) or not text.strip() or len(text)>2000 or data.get('style','cute')!='cute' or data.get('voice','feiyu')!='feiyu':
                    raise ValueError()
            except (ValueError,KeyError,TypeError):
                return self.send(400,{'error':'invalid_request'})
            with resident.lock:
                # Keep only a bounded in-memory audio history; never save dialogue.
                while len(resident.jobs)>=16:
                    completed = next((k for k,v in resident.jobs.items() if v['status'] in ('success','failed')),None)
                    if completed is None:
                        break
                    del resident.jobs[completed]
                job = secrets.token_hex(16)
                resident.jobs[job] = {'id':job,'status':'queued'}
                try:
                    resident.pending.put_nowait((job,text))
                except queue.Full:
                    del resident.jobs[job]
                    return self.send(429,{'error':'queue_full'})
            self.send(202,{'id':job})
    return Handler


if __name__=='__main__':
    resident = Resident()
    http = ThreadingHTTPServer(('127.0.0.1',9881), handler(resident))
    http.daemon_threads = True
    threading.Thread(target=resident.work,daemon=True).start()
    http.serve_forever()
