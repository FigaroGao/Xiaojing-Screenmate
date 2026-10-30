import * as kit from '/coopanion/kit/body.js';
import {createWhaleBody} from '/coopanion/whale/figure.js';

const preview=new URLSearchParams(location.search).has('preview');
const root=document.getElementById('root'),bubble=document.getElementById('bubble');
let host=null,body=null,state={},last=performance.now(),lastReport=0,lastRender=0,loaded=false;
let replyKey=null,replyUntil=0,bubbleHover=false,closedKey=null,lastScheme='',lastRoam='';
let requested=null,events=[],lastAction='neutral',pendingState=null;
function fail(error){document.getElementById('failure').textContent='动态形象暂时无法加载，请检查图形兼容性或使用旧渲染器。';if(host)host.failed(String(error?.message||error).slice(0,300));}
addEventListener('error',e=>fail(e.error||e.message));
addEventListener('unhandledrejection',e=>fail(e.reason));
function bounds(){return {W:innerWidth,H:innerHeight,floorY:innerHeight-8,S:preview?Math.min(innerWidth*.86/256,innerHeight*.94/256):(state.pet_size||218)/256};}
function setState(next){state={...state,...next};if(!body){pendingState=state;return;}
 const scheme=(state.pet_scheme||'deepseek')+'-'+(state.pet_outfit||'maid');
 if(scheme!==lastScheme){lastScheme=scheme;body.setScheme(scheme,{fade:state.reduced_motion?0:.35}).catch(fail);}
 const roam=preview||state.reduced_motion||state.activity==='quiet'?'off':state.activity==='lively'?'free':'calm';
 if(roam!==lastRoam){lastRoam=roam;body.set({roam});}
 body.set({thinking:!!state.thinking,status:state.thinking?'reading':null});body.resize();
 if(state.reply&&state.reply.at!==replyKey){replyKey=state.reply.at;replyUntil=performance.now()+Math.min(30000,Math.max(8000,state.reply.text.length*90));bubble.querySelector('p').textContent=state.reply.text;body.cue('cheer');}
}
function doAction(word){if(!body)return;body.set({hold:5});if(body.do(word)){lastAction=word;requested={word,until:performance.now()+4000};}}
function layoutReport(now){const layout=body.layout();let rectangle=null;
 if(!preview&&state.bubbles!==false&&replyKey!==null&&closedKey!==replyKey&&(now<replyUntil||bubbleHover)){
  bubble.hidden=false;const b=layout.bubble;const x=Math.max(8,Math.min(innerWidth-bubble.offsetWidth-8,b.x-bubble.offsetWidth/2));
  const y=Math.max(8,Math.min(innerHeight-bubble.offsetHeight-8,b.y-bubble.offsetHeight-14));bubble.style.left=x+'px';bubble.style.top=y+'px';rectangle={x,y,w:bubble.offsetWidth,h:bubble.offsetHeight};
 }else bubble.hidden=true;
 if(host&&now-lastReport>55){lastReport=now;host.report(JSON.stringify({...layout,bubbleRect:rectangle,action:requested&&now<requested.until?requested.word:null,events}));events=[];}
}
function frame(now){requestAnimationFrame(frame);const fps=preview?30:(state.render_fps||30);if(now-lastRender<1000/fps-1)return;
 const dt=Math.min(.05,(now-last)/1000);last=now;lastRender=now;
 try{if(state.speaking&&state.mouth>0.04)body.talk();body.step(dt);layoutReport(now);if(!loaded){loaded=true;document.body.dataset.ready='true';if(host)host.ready();}}
 catch(e){fail(e);}
}
const point=e=>({x:e.clientX,y:e.clientY});
root.addEventListener('pointerdown',e=>{if(e.button===0){body?.pointer('down',point(e));if(body?.layout().pressing)root.setPointerCapture(e.pointerId);}});
root.addEventListener('pointermove',e=>{if(preview||!host||!body?.layout().pressing)body?.pointer('move',point(e));});
root.addEventListener('pointerup',e=>body?.pointer('up',point(e)));
root.addEventListener('pointercancel',e=>body?.pointer('cancel',point(e)));
root.addEventListener('pointerleave',()=>body?.pointer('leave'));
root.addEventListener('dblclick',()=>host?.openPanel());
root.addEventListener('contextmenu',e=>{e.preventDefault();host?.menu();});
root.addEventListener('wheel',e=>{if(host){e.preventDefault();host.resizePet(e.deltaY<0?10:-10);}},{passive:false});
bubble.addEventListener('mouseenter',()=>bubbleHover=true);bubble.addEventListener('mouseleave',()=>bubbleHover=false);
document.getElementById('close').onclick=()=>{closedKey=replyKey;bubble.hidden=true;};
addEventListener('resize',()=>body?.resize());
addEventListener('message',e=>{if(e.origin!==location.origin||e.source!==parent||!preview)return;const m=e.data;if(m?.type==='companion-state')setState(m.state);if(m?.type==='companion-action')doAction(m.word);});
async function start(){
 if(!preview&&window.qt&&window.QWebChannel){host=await new Promise(resolve=>new QWebChannel(qt.webChannelTransport,channel=>resolve(channel.objects.host)));state=JSON.parse(await new Promise(resolve=>host.initial(resolve)));
  host.state.connect(value=>setState(JSON.parse(value)));host.action.connect(doAction);
  host.pointer.connect(value=>{const p=JSON.parse(value);body?.pointer('move',p);if(!p.down&&body?.layout().pressing)body.pointer('up',p);});
  host.transfer.connect(value=>{const t=JSON.parse(value);body?.shift(t.dx,t.dy);body?.resize();});
  host.home.connect(()=>{body?.do('stand');body?.place(innerWidth*.72,1,innerHeight-8);});
 }
 const position=state.position||{};
 body=await createWhaleBody(new URL('/coopanion/whale/',location.origin),{kit,scheme:(state.pet_scheme||'deepseek')+'-'+(state.pet_outfit||'maid'),host:{root,bounds,start:{x:preview?innerWidth/2:position.x,y:position.y,facing:position.facing||1,enter:'stand'},emit:(kind,detail)=>{events.push({kind,detail});if(kind==='touch')lastAction=detail.kind;},sound:()=>{}}});
 if(pendingState)setState(pendingState);else setState(state);
 new ResizeObserver(()=>body.resize()).observe(root);requestAnimationFrame(frame);
}
start().catch(fail);
