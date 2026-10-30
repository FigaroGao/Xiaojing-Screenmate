import * as kit from '/coopanion/kit/body.js';
import {createWhaleBody} from '/coopanion/whale/figure.js';
import {destination,route} from '/pet_motion.js';

const preview=new URLSearchParams(location.search).has('preview');
const root=document.getElementById('root'),bubble=document.getElementById('bubble');
let host=null,body=null,state={},last=performance.now(),lastReport=0,lastRender=0,loaded=false;
let replyKey=null,replyUntil=0,bubbleHover=false,closedKey=null,lastScheme='',lastRoam='';
let requested=null,events=[],lastAction='neutral',pendingState=null,lastThinking=null,lastSize=null;
let commandQueue=[],activeCommand=null,walkSequence=1,lastCommandGeneration=null;
function receipt(command,status,reason=''){
 const p=body?.layout();host?.commandResult(JSON.stringify({id:command.id,state:status,reason,position:p?{x:p.x/innerWidth,y:(p.y??innerHeight)/innerHeight}:null}));
}
function interrupt(reason){if(activeCommand){receipt(activeCommand,'interrupted',reason);activeCommand=null;}}
function nextWaypoint(){
 const command=activeCommand,point=command.points.shift();
 if(!point){
  const p=body.layout(),distance=Math.hypot(p.x-command.destination.x,(p.y??innerHeight)-command.destination.y);
  receipt(command,distance<6?'completed':'interrupted',distance<6?(command.adjusted?'arrived at safe adjusted target':'arrived'):'arrival did not match requested target');activeCommand=null;return;
 }
 command.walkId=++walkSequence;
 if(!body.move({to:'screenmate_point',params:point,run:command.pose==='run'},command.walkId)){
  receipt(command,'interrupted','movement refused by animation engine');activeCommand=null;
 }
}
function tickCommand(now){
 if(activeCommand){
  if(body.layout().pressing){interrupt('user dragging');return;}
  if(now-activeCommand.began>65000){if(activeCommand.walkId)body.stopWalk(activeCommand.walkId);receipt(activeCommand,'timeout','animation did not finish');activeCommand=null;return;}
  if(!activeCommand.points&&now-activeCommand.began>=5000){receipt(activeCommand,'completed','accepted action rendered for its display interval');activeCommand=null;}
  return;
 }
 const command=commandQueue[0];if(!command)return;
 if(Date.now()/1000-command.created>70){receipt(command,'timeout','command expired before rendering');commandQueue.shift();return;}
 if(!body||body.layout().busy){
  if(now-command.received>8000){receipt(command,'rejected','renderer busy for too long');commandQueue.shift();}
  return;
 }
 const moving=command.kind==='move'||['walk','run'].includes(command.pose);
 if(moving){
  try{
   const current=body.layout();
   const input=command.kind==='move'?command:{target:current.x<innerWidth/2?'right':'left'};
   const target=destination(input,innerWidth,innerHeight,state.pet_size||218,state.pet_avoid_center!==false);
   activeCommand={...command,points:route(current,target,innerWidth,innerHeight,state.pet_avoid_center!==false),destination:target,adjusted:target.adjusted,began:now};
   commandQueue.shift();body.set({hold:70});receipt(activeCommand,'started','movement accepted');nextWaypoint();
  }catch(error){receipt(command,'rejected',String(error.message));commandQueue.shift();}
 }else if(body.do(command.pose)){
  commandQueue.shift();activeCommand={...command,began:now};body.set({hold:6});
  requested={word:command.pose,until:now+5000};receipt(command,'started','animation engine accepted action');
 }else if(now-command.received>8000){receipt(command,'rejected','animation refused action');commandQueue.shift();}
}
function fail(error){document.getElementById('failure').textContent='动态形象暂时无法加载，请检查图形兼容性或使用旧渲染器。';if(host)host.failed(String(error?.message||error).slice(0,300));}
addEventListener('error',e=>fail(e.error||e.message));
addEventListener('unhandledrejection',e=>fail(e.reason));
function bounds(){return {W:innerWidth,H:innerHeight,floorY:innerHeight-8,S:preview?Math.min(innerWidth*.86/256,innerHeight*.94/256):(state.pet_size||218)/256};}
function setState(next){state={...state,...next};if(!body){pendingState=state;return;}
 if(lastCommandGeneration!==state.command_generation){
  lastCommandGeneration=state.command_generation;
  if(activeCommand){if(activeCommand.walkId)body.stopWalk(activeCommand.walkId);receipt(activeCommand,'cancelled','watching session changed');activeCommand=null;}
  for(const command of commandQueue)receipt(command,'cancelled','watching session changed');commandQueue=[];
 }
 const scheme=(state.pet_scheme||'deepseek')+'-'+(state.pet_outfit||'maid');
 if(scheme!==lastScheme){lastScheme=scheme;body.setScheme(scheme,{fade:state.reduced_motion?0:.35}).catch(fail);}
 const roam=preview||state.pet_avoid_center!==false||state.reduced_motion||state.activity==='quiet'?'off':state.activity==='lively'?'free':'calm';
 if(roam!==lastRoam){lastRoam=roam;body.set({roam});}
 if(lastThinking!==!!state.thinking){lastThinking=!!state.thinking;body.set({thinking:lastThinking,status:lastThinking?'reading':null});}
 if(lastSize!==state.pet_size){lastSize=state.pet_size;body.resize();}
 if(state.reply&&state.reply.at!==replyKey){replyKey=state.reply.at;replyUntil=performance.now()+Math.min(30000,Math.max(8000,state.reply.text.length*90));bubble.querySelector('p').textContent=state.reply.text;body.cue('cheer');}
}
function doAction(word){if(!body)return;body.set({hold:5});if(body.do(word)){lastAction=word;requested={word,until:performance.now()+4000};}}
function layoutReport(now){const layout=body.layout();let rectangle=null;
 for(const event of events){
  if(activeCommand?.points&&event.detail?.walkId===activeCommand.walkId){
   if(event.kind==='arrived')nextWaypoint();
   else if(event.kind==='interrupted')interrupt('movement interrupted');
  }
 }
 if(!preview&&state.bubbles!==false&&replyKey!==null&&closedKey!==replyKey&&(now<replyUntil||bubbleHover||state.speaking)){
  bubble.hidden=false;const b=layout.bubble;
  bubble.style.maxWidth=state.pet_avoid_center!==false?Math.max(120,Math.min(340,innerWidth*.28-16))+'px':'340px';
  const x=state.pet_avoid_center!==false?(layout.x<innerWidth/2?8:innerWidth-bubble.offsetWidth-8):Math.max(8,Math.min(innerWidth-bubble.offsetWidth-8,b.x-bubble.offsetWidth/2));
  const y=Math.max(8,Math.min(innerHeight-bubble.offsetHeight-8,b.y-bubble.offsetHeight-14));bubble.style.left=x+'px';bubble.style.top=y+'px';rectangle={x,y,w:bubble.offsetWidth,h:bubble.offsetHeight};
 }else bubble.hidden=true;
 if(host&&now-lastReport>55){lastReport=now;host.report(JSON.stringify({...layout,bubbleRect:rectangle,action:requested&&now<requested.until?requested.word:null,events}));events=[];}
}
function frame(now){requestAnimationFrame(frame);const fps=preview?30:(state.render_fps||30);if(now-lastRender<1000/fps-1)return;
 if(preview&&state.preview_active===false){last=now;return;}
 const dt=Math.min(.05,(now-last)/1000);last=now;lastRender=now;
 try{
  const p=body.layout();
  if(!preview&&state.pet_avoid_center!==false&&!p.busy&&!p.pressing&&!activeCommand&&p.x>.3*innerWidth-(state.pet_size||218)/2&&p.x<.7*innerWidth+(state.pet_size||218)/2){
   const safe=destination({target:p.x<innerWidth/2?'left':'right'},innerWidth,innerHeight,state.pet_size||218,true);body.place(safe.x,1,p.y);
  }
  if(state.speaking&&state.mouth>0.04)body.talk();body.step(dt);tickCommand(now);layoutReport(now);if(!loaded){loaded=true;document.body.dataset.ready='true';if(host)host.ready();}}
 catch(e){fail(e);}
}
const point=e=>({x:e.clientX,y:e.clientY});
root.addEventListener('pointerdown',e=>{if(e.button===0){interrupt('user interaction');body?.pointer('down',point(e));if(body?.layout().pressing)root.setPointerCapture(e.pointerId);}});
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
  host.command.connect(value=>commandQueue.push({...JSON.parse(value),received:performance.now()}));
  host.pointer.connect(value=>{const p=JSON.parse(value);body?.pointer('move',p);if(!p.down&&body?.layout().pressing)body.pointer('up',p);});
  host.transfer.connect(value=>{const t=JSON.parse(value);body?.shift(t.dx,t.dy);body?.resize();});
  host.home.connect(()=>{body?.do('stand');body?.place(innerWidth*.72,1,innerHeight-8);});
 }
 const position=state.position||{};
 const freeKit={...kit,createBody:(host,opts)=>kit.createBody(host,{...opts,ground:'free',moves:{...opts.moves,screenmate_point:params=>params}})};
 body=await createWhaleBody(new URL('/coopanion/whale/',location.origin),{kit:freeKit,scheme:(state.pet_scheme||'deepseek')+'-'+(state.pet_outfit||'maid'),host:{root,bounds,start:{x:preview?innerWidth/2:position.x,y:position.y,facing:position.facing||1,enter:'stand'},emit:(kind,detail)=>{events.push({kind,detail});if(kind==='touch')lastAction=detail.kind;},sound:()=>{}}});
 if(pendingState)setState(pendingState);else setState(state);
 new ResizeObserver(()=>body.resize()).observe(root);requestAnimationFrame(frame);
}
start().catch(fail);
