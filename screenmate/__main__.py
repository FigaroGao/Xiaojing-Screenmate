import argparse
import threading
from pathlib import Path

from .core import Engine
from .server import create_server


def main():
    parser = argparse.ArgumentParser(description="小鲸桌面陪伴端")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=17860)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--open-panel", action="store_true", help="启动后打开原生小窝窗口")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "runtime")
    args = parser.parse_args()
    engine = Engine(args.data_dir)
    server = create_server(engine, args.host, args.port)
    worker = threading.Thread(target=engine.run, daemon=True)
    worker.start()
    server_thread = None
    print(f"Screenmate: http://127.0.0.1:{args.port}", flush=True)
    print(f"Pairing settings: {engine.path} (keep private)", flush=True)
    try:
        if args.headless:
            server.serve_forever()
        else:
            from .pet import Pet
            from .voice import FeiyuVoice
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            pet = Pet(engine, FeiyuVoice(engine.config), f"http://127.0.0.1:{args.port}")
            print(f"Pet excluded from capture: {pet.capture_excluded}", flush=True)
            if args.open_panel:
                pet.open_panel()
            pet.run()
    except KeyboardInterrupt:
        pass
    finally:
        engine.close()
        if server_thread:
            server.shutdown()
            server_thread.join(timeout=3)
        server.server_close()
        worker.join(timeout=3)


if __name__ == "__main__":
    main()
