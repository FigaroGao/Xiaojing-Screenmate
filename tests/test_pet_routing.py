import json,shutil,subprocess
from pathlib import Path
import pytest

@pytest.mark.skipif(not shutil.which('node'),reason='Node needed for real browser routing module')
def test_real_route_module_preserves_coordinates_and_avoids_middle():
    path=Path(__file__).parents[1]/'screenmate/web/pet_motion.js'
    code="""
import {readFile} from 'node:fs/promises';
const module=await import('data:text/javascript;base64,'+Buffer.from(await readFile(PATH)).toString('base64'));
const center=module.destination({target:'coordinates',x:.5,y:.5},1920,1080,218,true);
if(!center.adjusted||center.x>1920*.3&&center.x<1920*.7)throw Error('protected target not projected');
const exact=module.destination({target:'coordinates',x:.5,y:.5},1920,1080,218,false);
if(exact.x!==960||exact.y!==540)throw Error('unprotected coordinates changed');
const target=module.destination({target:'left'},1920,1080,218,true);
const route=module.route({x:1800,y:500},target,1920,1080,true);
if(route.length!==3||route[0].y!==1072||route[1].y!==1072)throw Error('route crosses center');
console.log('routing passed');
""".replace('PATH',json.dumps(str(path)))
    r=subprocess.run(['node','--input-type=module'],input=code,text=True,capture_output=True,timeout=10)
    assert r.returncode==0,r.stderr
