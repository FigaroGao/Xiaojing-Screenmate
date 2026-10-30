"""Package only extension sources; never include runtime credentials."""
from pathlib import Path
import zipfile,json

def main():
    root=Path(__file__).resolve().parents[1]
    source=root/'browser-extension'
    json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    target=root/'dist/xiaojing-browser-extension.zip';target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for path in source.iterdir():
            if path.is_file() and path.suffix in ('.js','.json','.html','.png','.md'):z.write(path,'xiaojing-browser-extension/'+path.name)
    print(str(target))

if __name__=='__main__':main()
