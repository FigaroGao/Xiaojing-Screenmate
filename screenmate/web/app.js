"use strict";
const $ = (id) => document.getElementById(id);
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
          ? "设置未保存，请检查输入范围与格式"
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
    : "现在先安静陪着你";
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
  $("pose-label").textContent=status.companion?.ready?'小鲸 · '+status.companion.label:'动态模型等待载入';
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
  if (initial || !editing.voice) {
    $("voice-url").value = p.voice_url || "http://127.0.0.1:9880";
    $("voice-style").value = p.voice_style || "cute";
  }
}
async function refresh() {
  if (busyRefresh) return;
  busyRefresh = true;
  try {
    apply(await api("status"));
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
      document
        .querySelectorAll("[data-page]")
        .forEach((el) => el.classList.toggle("active", el === button));
      document
        .querySelectorAll(".page")
        .forEach((el) => (el.hidden = el.id !== "page-" + page));
      $("page-title").textContent = button.textContent.trim();
      window.scrollTo({ top: 0, behavior: "instant" });
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
    },
    "陪伴偏好已保存",
  );
  editing.appearance = false;
  document.body.classList.toggle("reduced-motion", reduced);
});
async function performPose(pose) {
  await api("pet/action", { pose });
  for (const id of ["hero-pet", "stage-pet"])
    $(id).contentWindow.postMessage({type:'companion-action',word:pose},location.origin);
  $("stage-pose").textContent = poses[pose];
  toast("让小鲸" + poses[pose] + "一下");
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
  for(const id of ['hero-pet','stage-pet'])$(id).contentWindow.postMessage({type:'companion-state',state},location.origin);
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
  toast("已复制本机地址；平板连接需改用电脑局域网地址");
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
