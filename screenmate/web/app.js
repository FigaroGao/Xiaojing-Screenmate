"use strict";
const $ = (id) => document.getElementById(id);
let pendingChat = null;
let pendingPetCommand=null, voiceBank=[],lastAuxRefresh=0,activePage='watch',savingGuard=false;
window.addEventListener('DOMContentLoaded',()=>{
  $('send-desktop-chat').onclick=async()=>{
    const text=$('desktop-chat').value.trim();if(!text)return;
    const button=$('send-desktop-chat');button.disabled=true;
    try{pendingChat=(await api('chat',{text})).id;$('desktop-chat').value='';$('desktop-chat-state').textContent='已排队，等待平板小鲸回应'}
    catch(e){$('desktop-chat-state').textContent='发送未确认，请先查看连接状态，避免重复发送'}
    finally{button.disabled=false}
  };
});
const icons = {
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  heart:
    '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
  sound:
    '<path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
  link: '<path d="m10 13 4-4m-6 6-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 3 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(1 1)"/>',
  play: '<path d="m8 4 11 8-11 8V4Z"/>',
  pause: '<path d="M8 5v14m8-14v14"/>',
  text: '<path d="M4 5h16M4 10h16M4 15h10M4 20h7"/>',
  image:
    '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
  layers:
    '<path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5"/>',
  frame: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.5"/>',
  screen:
    '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/>',
};
function svg(name) {
  return (
    '<svg viewBox="0 0 24 24" aria-hidden="true">' +
    (icons[name] || icons.info) +
    "</svg>"
  );
}
document
  .querySelectorAll("[data-icon]")
  .forEach((el) => (el.innerHTML = svg(el.dataset.icon)));
let poses = {};
let latestStatus = null;
let token = "",
  enabled = false,
  poller = null,
  lastPose = "",
  busyRefresh = false,
  toastTimer;
const editing = { watch: false, appearance: false, voice: false };
for (const id of ["interval", "bbox"])
  $(id).addEventListener("input", () => (editing.watch = true));
for (const id of ["pet-size", "activity", "reduced-motion", "bubbles", "pet-scheme", "pet-outfit", "render-fps", "input-passthrough"])
  $(id).addEventListener("input", () => (editing.appearance = true));
for (const id of ["voice-url", "voice-key", "voice-style"])
  $(id).addEventListener("input", () => (editing.voice = true));
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 3400);
}
async function api(path, body) {
  const response = await fetch("/v1/" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok)
    throw Error(
      response.status === 401
        ? "连接已失效，请重新配对"
        : response.status === 400
          ? "请求未执行，请检查输入，并确认桌宠或播放器已就绪"
          : "暂时无法连接桌面端",
    );
  return response.json();
}
function relativeTime(at) {
  if (!at) return "还没有开始";
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - at));
  return seconds < 5
    ? "刚刚更新"
    : seconds < 60
      ? seconds + " 秒前更新"
      : Math.floor(seconds / 60) + " 分钟前更新";
}
async function connect(value) {
  token = value.trim();
  $("pair-error").textContent = "";
  try {
    const status = await api("status");
    poses = (await api("companion/catalog")).actions;
    buildPoseGrid();
    $("pairing").hidden = true;
    $("app").hidden = false;
    $("pair-token").value = "";
    apply(status, true);
    loadVoiceBank();loadSessions();
    if (!poller) poller = setInterval(refresh, 1000);
  } catch (e) {
    $("pair-error").textContent = e.message;
    $("pairing").hidden = false;
    $("app").hidden = true;
  }
}
window.Desktop = { connect };
$("pair-form").addEventListener("submit", (e) => {
  e.preventDefault();
  connect($("pair-token").value);
});
function apply(status, initial = false) {
  latestStatus = status;
  enabled = status.enabled;
  $("watch-toggle").disabled = false;
  $("watch-state").classList.toggle("watching", enabled);
  $("watch-state").innerHTML =
    "<b></b>" + (enabled ? "持续陪看中" : "观看已暂停");
  $("watch-toggle").innerHTML =
    svg(enabled ? "pause" : "play") +
    "<span>" +
    (enabled ? "暂停观看" : "开启持续陪看") +
    "</span>";
  $("hero-state").textContent = enabled
    ? "正在按你的节奏看屏幕"
    : "截图已暂停，桌宠已隐藏，聊天仍可用";
  $('session-elapsed').textContent=status.session_started?duration(Date.now()/1000-status.session_started):'尚未开始';
  $('sampling-rate').textContent=status.interval+' 秒 / 次';
  $('vision-rate').textContent=status.bridge?.vision_min_seconds?status.bridge.vision_min_seconds+' 秒':'等待平板状态';
  $('initiative-rate').textContent=status.bridge?.initiative_enabled?duration(status.bridge.initiative_seconds)+' / 次判断':status.bridge?.connected_at?'已关闭':'等待平板状态';
  $("capture-state").textContent = status.error
    ? "等待有效内容"
    : status.has_observation
      ? relativeTime(status.observation_time)
      : enabled
        ? "等待下一次观察"
        : "还没有开始";
  const bridgeAt = status.bridge?.connected_at;
  const connected = bridgeAt && Date.now() / 1000 - bridgeAt < 120;
  $("bridge-state").textContent = connected
    ? "AstrBot 已连接"
    : "等待 AstrBot 连接";
  $("bridge-badge").textContent = connected ? "已连接" : "等待连接";
  $("voice-state").textContent = status.voice?.checked
    ? status.voice.available
      ? "本地语音已就绪"
      : "服务尚未就绪"
    : status.voice_configured
      ? "已保存，待检测"
      : "尚未配置";
  const vs=status.voice||{};
  $('toggle-tts').dataset.enabled=String(!!vs.enabled);
  $('toggle-tts').textContent=vs.enabled?'关闭语音':vs.state==='stopping'?'正在关闭…':'开启语音';
  $('toggle-tts').disabled=vs.state==='stopping';
  $('tts-state').textContent=vs.playback_error||vs.message||'语音已关闭；陪看和文字聊天仍然可用';
  $('voice-state').textContent=({off:'已关闭',loading:'正在加载',ready:'已就绪',failed:'加载失败',stopping:'正在关闭'})[vs.state]||'已关闭';
  if (status.voice?.checked)
    $("voice-result").querySelector("span").textContent =
      status.voice.message || "检测完成";
  $("capture-error").hidden = !status.error;
  $("capture-error").textContent = status.error || "";
  if (status.reply) {
    $("reply").textContent = status.reply.text;
    $("reply-time").textContent = relativeTime(status.reply.at).replace(
      "更新",
      "收到",
    );
  }
  $("pose-label").textContent=status.companion?.visible?'桌宠已显示 · '+status.companion.label:'仅形象预览 · 桌宠隐藏';
  $('pet-visibility').textContent=status.companion?.visible?'桌宠已显示':enabled?'桌宠准备中':'暂停中 · 桌宠隐藏';
  document.querySelectorAll('[data-target],#move-to-app').forEach(button=>button.disabled=!enabled||!status.companion?.ready||status.companion?.visible===false);
  $("stage-pose").textContent=status.companion?.label||'待机';
  $("renderer-warning").hidden=!status.companion?.error;
  $("renderer-warning").textContent=status.companion?.error||'';
  updatePreviews(status);
  if (initial || !editing.watch) {
    $("interval").value = status.interval;
    $("interval-display").textContent = status.interval;
    $("skip").checked = status.skip_unchanged;
    $("bbox").value = status.monitor_bbox?.join(",") || "";
    markMode(status.mode);
    markInterval(status.interval);
  }
  const p = status.preferences || {};
  if (initial || !editing.appearance) {
    $("pet-size").value = p.pet_size || 218;
    $("size-value").textContent = (p.pet_size || 218) + " px";
    $("activity").value = p.activity || "balanced";
    $("reduced-motion").checked = p.reduced_motion || false;
    $("bubbles").checked = p.bubbles !== false;
    $("pet-scheme").value=p.pet_scheme||'deepseek';
    $("pet-outfit").value=p.pet_outfit||'maid';
    $("render-fps").value=p.render_fps||30;
    $("input-passthrough").checked=p.input_passthrough!==false;
    document.body.classList.toggle("reduced-motion", p.reduced_motion || false);
  }
  if(!savingGuard)$('avoid-center').checked=p.pet_avoid_center!==false;
  document.querySelector('.position-pad>span').textContent=p.pet_avoid_center!==false?'中心保护':'自由位置';
  if (initial || !editing.voice) {
    $("voice-url").value = p.voice_url || "http://127.0.0.1:9881";
    $("voice-style").value = p.voice_style || "cute";
  }
}
async function refresh() {
  if (busyRefresh) return;
  busyRefresh = true;
  try {
    apply(await api("status"));
    if(pendingChat){
      const state=(await api('chat/status')).jobs[pendingChat];
      $('desktop-chat-state').textContent=({queued:'已排队，等待平板连接',dispatched:'小鲸正在回复',replied:'小鲸已回复，请看回复气泡',cancelled:'这次接话已取消'})[state]||'暂无回执，请检查连接';
      if(state==='replied'||state==='cancelled')pendingChat=null;
    }
    if(pendingPetCommand)await refreshCommand();
    if(Date.now()-lastAuxRefresh>10000){lastAuxRefresh=Date.now();if(activePage==='sessions')loadSessions();}
  } catch (e) {
    $("watch-state").classList.remove("watching");
    $("watch-state").innerHTML = "<b></b>桌面连接中断";
    $("bridge-state").textContent = "请检查桌面端是否运行";
    $("watch-toggle").disabled = true;
  } finally {
    busyRefresh = false;
  }
}
function markMode(mode) {
  document.querySelectorAll("[data-mode]").forEach((el) => {
    const selected = el.dataset.mode === mode;
    el.classList.toggle("selected", selected);
    el.setAttribute("aria-pressed", selected);
  });
  $("mode-note").textContent = {
    text: "文字模式不截屏，需要浏览器扩展发送当前页可见文字。",
    vision: "视觉模式会按频率截图，交给已配置的视觉模型识读。",
    mixed: "混合模式会同时获取截图与浏览器文字。",
  }[mode];
}
function markInterval(seconds) {
  document.querySelectorAll("[data-interval]").forEach((el) => {
    const selected = Number(el.dataset.interval) === Number(seconds);
    el.classList.toggle("active", selected);
    el.setAttribute("aria-pressed", selected);
  });
  $("interval-display").textContent = seconds;
}
async function save(values, message) {
  await api("settings", values);
  if (message) toast(message);
  await refresh();
}
function action(handler) {
  return async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await handler(event);
    } catch (e) {
      toast(e.message);
    } finally {
      button.disabled = false;
    }
  };
}
document.querySelectorAll("[data-page]").forEach(
  (button) =>
    (button.onclick = () => {
      const page = button.dataset.page;
      activePage=page;
      document
        .querySelectorAll("[data-page]")
        .forEach((el) => el.classList.toggle("active", el === button));
      document
        .querySelectorAll(".page")
        .forEach((el) => (el.hidden = el.id !== "page-" + page));
      $("page-title").textContent = button.textContent.trim();
      window.scrollTo({ top: 0, behavior: "instant" });
      if(page==='sessions')loadSessions();
      if(page==='voice')loadVoiceBank();
    }),
);
$("watch-toggle").onclick = action(async () => {
  await api("watching", { enabled: !enabled });
  await refresh();
  toast(enabled ? "持续陪看已开启" : "已暂停观看");
});
document.querySelectorAll("[data-mode]").forEach(
  (button) =>
    (button.onclick = action(async () => {
      await save({ mode: button.dataset.mode });
      markMode(button.dataset.mode);
      toast("观察方式已更新");
    })),
);
document.querySelectorAll("[data-interval]").forEach(
  (button) =>
    (button.onclick = action(async () => {
      const seconds = Number(button.dataset.interval);
      await save({ interval: seconds });
      $("interval").value = seconds;
      markInterval(seconds);
      toast("现在每 " + seconds + " 秒看一眼");
    })),
);
$("save-interval").onclick = action(async () => {
  const seconds = Number($("interval").value);
  if (!Number.isFinite(seconds) || seconds < 1 || seconds > 3600)
    throw Error("观察间隔请填写 1 至 3600 秒");
  await save({ interval: seconds }, "观察间隔已保存");
  editing.watch = false;
  markInterval(seconds);
});
$("skip").onchange = async () => {
  try {
    await save({ skip_unchanged: $("skip").checked }, "重复内容设置已保存");
  } catch (e) {
    $("skip").checked = !$("skip").checked;
    toast(e.message);
  }
};
$("save-region").onclick = action(async () => {
  const value = $("bbox").value.trim();
  const bbox = value ? value.split(/[,，]/).map((n) => Number(n.trim())) : null;
  if (
    bbox &&
    (bbox.length !== 4 ||
      bbox.some((n) => !Number.isInteger(n)) ||
      bbox[2] <= bbox[0] ||
      bbox[3] <= bbox[1])
  )
    throw Error("请填写 左,上,右,下，例如 0,0,1280,720");
  await save({ monitor_bbox: bbox }, "截图范围已保存");
  editing.watch = false;
});
$("pet-size").oninput = () => {
  $("size-value").textContent = $("pet-size").value + " px";
};
$("save-appearance").onclick = action(async () => {
  const reduced = $("reduced-motion").checked;
  await save(
    {
      pet_size: Number($("pet-size").value),
      activity: $("activity").value,
      reduced_motion: reduced,
      bubbles: $("bubbles").checked,
      pet_scheme: $("pet-scheme").value,
      pet_outfit: $("pet-outfit").value,
      render_fps: Number($("render-fps").value),
      input_passthrough: $("input-passthrough").checked,
      pet_avoid_center:$('avoid-center').checked,
    },
    "陪伴偏好已保存",
  );
  editing.appearance = false;
  document.body.classList.toggle("reduced-motion", reduced);
});
async function performPose(pose) {
  if(!$('preview-only').checked){
    const record=await api('pet/action',{pose});pendingPetCommand=record.id;
    $('pet-command-state').textContent='已排队，等待桌宠执行';
  }
  for (const id of ["hero-pet", "stage-pet"])
    $(id).contentWindow.postMessage({type:'companion-action',word:pose},location.origin);
  $("stage-pose").textContent = poses[pose];
  toast($('preview-only').checked?'仅预览：'+poses[pose]:'动作已排队，请查看执行回执');
}
document
  .querySelectorAll("[data-pose]")
  .forEach(
    (button) =>
      (button.onclick = action(() => performPose(button.dataset.pose))),
  );
function buildPoseGrid(){
$("pose-grid").textContent='';
for (const [pose, label] of Object.entries(poses)) {
  const button = document.createElement("button");
  button.className = "pose-button";
  button.innerHTML = svg(pose==='love'?'heart':'play');
  const text=document.createElement('span');text.textContent=label;button.appendChild(text);
  button.setAttribute("aria-label", "预览动作：" + label);
  button.onclick = action(() => performPose(pose));
  $("pose-grid").appendChild(button);
}
}
function updatePreviews(status){
  const state={...status.preferences,activity:'quiet',speaking:status.companion?.speaking||false,mouth:status.companion?.mouth||0};
  for(const id of ['hero-pet','stage-pet'])$(id).contentWindow.postMessage({type:'companion-state',state:{...state,preview_active:!$(id).closest('.page').hidden}},location.origin);
}
for(const id of ['hero-pet','stage-pet'])$(id).addEventListener('load',()=>{if(latestStatus)updatePreviews(latestStatus)});
async function saveVoice() {
  const values = {
    voice_url: $("voice-url").value.trim(),
    voice_style: $("voice-style").value,
  };
  if ($("voice-key").value) values.voice_key = $("voice-key").value;
  await api("settings", values);
  $("voice-key").value = "";
  editing.voice = false;
  await refresh();
}
$("save-voice").onclick = action(async () => {
  await saveVoice();
  toast("声音设置已保存");
});
$("test-voice").onclick = action(async () => {
  await saveVoice();
  $("voice-result").querySelector("span").textContent = "正在检查声音服务…";
  await api("voice/test", {});
  await refresh();
});
$("preview-voice").onclick = action(async () => {
  await saveVoice();
  await api("voice/preview", {});
  toast("已开始本地合成，首次加载模型需要一些时间");
});
$("server-address").textContent = location.origin;
$("copy-address").onclick = action(async () => {
  await navigator.clipboard.writeText(location.origin);
  toast("已复制本机地址；USB 平板连接使用 ADB reverse 隧道");
});
$("open-preview").onclick = action(async () => {
  const { observation } = await api("observations/latest");
  $("preview-image").hidden = true;
  $("preview-text").hidden = true;
  $("preview-empty").hidden = !!observation;
  $("preview-meta").textContent = observation
    ? new Date(observation.captured_at * 1000).toLocaleString("zh-CN") +
      " · " +
      { text: "文字", vision: "画面", mixed: "图文" }[observation.mode]
    : "不使用旧画面冒充当前观察";
  if (observation?.image_base64) {
    $("preview-image").src =
      "data:image/jpeg;base64," + observation.image_base64;
    $("preview-image").hidden = false;
  }
  if (observation?.text) {
    $("preview-text").textContent =
      (observation.text.title || "") + "\n\n" + (observation.text.text || "");
    $("preview-text").hidden = false;
  }
  $("preview-dialog").showModal();
});
$("close-preview").onclick = () => {
  $("preview-dialog").close();
  $("preview-image").removeAttribute("src");
  $("preview-text").textContent = "";
};
$("preview-dialog").addEventListener("close", () => {
  $("preview-image").removeAttribute("src");
  $("preview-text").textContent = "";
});

function duration(seconds){
  const value=Math.max(0,Math.floor(seconds||0)),h=Math.floor(value/3600),m=Math.floor(value%3600/60),s=value%60;
  return (h?h+'小时':'')+(m?m+'分':'')+(s||!h&&!m?s+'秒':'');
}
function element(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}
async function refreshCommand(){
  try{
    const record=await api('pet/commands/'+pendingPetCommand);
    const labels={queued:'已排队，尚未执行',started:'正在执行，尚未完成',completed:'执行已完成',rejected:'未执行：目标不明确或动画忙碌',interrupted:'执行已中断',cancelled:'已取消',timeout:'未收到完成回执'};
    $('pet-command-state').textContent=(labels[record.state]||'状态未知')+(record.reason?.includes('adjusted')?' · 已调整到安全位置':'');
    $('pet-command-state').dataset.state=record.state;
    if(!['queued','started'].includes(record.state))pendingPetCommand=null;
  }catch(e){$('pet-command-state').textContent='未能查询回执，请检查连接；不代表动作完成';pendingPetCommand=null;}
}
async function movePet(payload){
  const record=await api('pet/move',payload);pendingPetCommand=record.id;
  $('pet-command-state').textContent='移动已排队，等待开始';
}
document.querySelectorAll('[data-target]').forEach(button=>button.onclick=action(()=>movePet({target:button.dataset.target})));
$('move-to-app').onclick=action(async()=>{
  const app=$('move-app').value.trim();if(!app)throw Error('先填写准确的程序名，例如 chrome.exe');
  await movePet({target:'app',app,side:$('move-side').value});
});
$('avoid-center').onchange=async()=>{
  savingGuard=true;
  try{await save({pet_avoid_center:$('avoid-center').checked},'中心保护已更新');}
  catch(e){$('avoid-center').checked=latestStatus?.preferences?.pet_avoid_center!==false;toast(e.message);}
  finally{savingGuard=false;}
};

async function loadVoiceBank(){
  try{voiceBank=(await api('voice/bank')).phrases;$('bank-count').textContent=voiceBank.length+' 段';renderVoiceBank();}
  catch(e){$('bank-status').textContent='语音库读取失败，请检查本机连接';}
}
function renderVoiceBank(){
  const query=$('bank-search').value.trim(),filter=$('bank-filter').value,container=$('voice-bank');container.replaceChildren();
  const aliases={美食:['食物','做饭','馋','锅'],比赛:['比赛','游戏','击杀','操作'],游戏:['游戏','比赛','击杀','操作'],搞笑:['搞笑','好笑','表情','反转'],动物:['动物','小家伙','团子'],风景:['风景','海景','画面好看'],线索:['线索','解谜','疑点']};
  const terms=aliases[query]||[query];
  const rows=voiceBank.filter(row=>(filter==='all'||row.automatic===(filter==='auto'))&&(!query||terms.some(term=>(row.text+' '+row.when).includes(term))));
  $('bank-count').textContent=rows.length+' / '+voiceBank.length+' 段';
  for(const row of rows){
    const card=element('article',undefined,'voice-clip');
    const title=element('div',undefined,'clip-title');title.append(element('strong',row.text),element('span',row.automatic?'场景反应':'仅手动','tag'));
    const detail=element('p',row.when,'fine'),button=element('button','试听','button secondary small');
    button.onclick=action(async()=>{
      await api('voice/bank/preview',{id:row.id});
      $('bank-status').textContent='已请求试听「'+row.text+'」；播放器忙时不会打断原回复';
    });
    card.append(title,detail,button);container.append(card);
  }
  if(!rows.length)container.append(element('div',voiceBank.length?'没有匹配的语音':'还没有预存语音文件','empty-state'));
}
$('bank-search').addEventListener('input',renderVoiceBank);
$('bank-filter').addEventListener('change',renderVoiceBank);
$('stop-voice').onclick=action(async()=>{await api('voice/stop',{});$('bank-status').textContent='已请求停止本机播放';});
$('toggle-tts').onclick=action(async()=>{await api('voice/enabled',{enabled:$('toggle-tts').dataset.enabled!=='true'});await refresh();});

async function loadSessions(){
  try{
    const rows=(await api('sessions')).sessions.filter(row=>!String(row.reason||'').startsWith('maintenance'));
    const list=$('session-list');list.replaceChildren();
    for(const row of rows){
      const card=element('article',undefined,'card session-card'),head=element('div',undefined,'card-heading');
      const fmt=stamp=>new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Hong_Kong',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(stamp*1000));
      const stored=/^\d+$/.test(row.ack||''),state=!row.ended?'进行中':stored?'已存入原记忆':'尚未收到写入回执';
      head.append(element('strong',fmt(row.started)),element('span',state,'tag'));
      const timing=element('p',(row.ended?'结束 '+fmt(row.ended):'仍在陪看')+' · '+duration((row.ended||Date.now()/1000)-row.started)+(row.reason==='interrupted'?' · 异常中断，按最后采集时间计时':''),'session-timing');
      card.append(head,timing);
      if(row.summary){const text=row.summary.startsWith('陪看开始：')?row.summary.split('\n').slice(1).join('\n'):row.summary;card.append(element('p',text,'session-summary'));}
      else card.append(element('p',stored?'总结已保存，正文等待平板同步。':row.ended?'结束约90秒后开始收尾；断连或写入异常时会保留待处理记录。':'本场细节独立记录，结束后才生成总结。','fine'));
      if(stored)card.append(element('small','长期记忆 #'+row.ack,'fine'));
      list.append(card);
    }
    if(!rows.length)list.append(element('div','还没有陪看记录。开启持续陪看后，会开始新的一场。','empty-state'));
  }catch(e){$('session-list').replaceChildren(element('div','暂时无法读取记录，请确认本机服务正在运行。','empty-state'));}
}
$('refresh-sessions').onclick=action(loadSessions);
$('download-extension').onclick=action(async()=>{
  const response=await fetch('/v1/extension/download',{headers:{Authorization:'Bearer '+token},cache:'no-store'});
  if(!response.ok)throw Error('暂时无法获取扩展压缩包');
  const url=URL.createObjectURL(await response.blob()),a=element('a');a.href=url;a.download='xiaojing-browser-extension.zip';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
  toast('已请求下载；解压后在浏览器扩展页加载文件夹');
});
// Keep daily use first, while retaining service credentials in a collapsed section.
{
  const page=$('page-voice'),columns=page.querySelector('.two-columns'),bank=page.querySelector('.bank-section');
  const details=element('details',undefined,'voice-advanced'),summary=element('summary','语音服务设置与合成试听');
  columns.before(details);details.append(summary,columns);details.before(bank);
}
{
  const page=$('page-companion'),layout=page.querySelector('.companion-layout'),appearance=page.querySelector('.appearance-settings'),move=page.querySelector('.move-card');
  const controls=element('div',undefined,'companion-controls');appearance.before(controls);controls.append(move);
  const guard=$('avoid-center').closest('label');move.querySelector('.move-layout').before(guard);
  const fields=move.querySelector('.move-fields'),receipt=$('pet-command-state');
  move.append(receipt);
  const appDetails=element('details',undefined,'move-advanced');fields.before(appDetails);appDetails.append(element('summary','靠近指定程序窗口'),fields);
  const appearanceDetails=element('details',undefined,'appearance-advanced');appearanceDetails.append(element('summary','外观与动画偏好'),appearance);controls.append(appearanceDetails);
}
