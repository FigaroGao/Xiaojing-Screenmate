# 小鲸 · Xiaojing Screenmate

小鲸在电脑上的桌面陪伴端。持续获取屏幕或浏览器文字，把观察交给 AstrBot 中的小鲸，再通过桌宠气泡和本地语音表达。

**v0.2.0：Q版桌宠与原生小窝。** 新项目独立开发，不覆盖旧 ScreenMate，也不携带小鲸的私人记忆、人格、凭据或聊天记录。

## 这一版的体验

- 复用 `dsh-pet-dafeiyu` 的 18 种 Q版鲸鱼娘姿态，保留 `dsh-co-pet` 的原生桌宠引擎；素材原图不修改，也不打包上传到本仓。
- 待机呼吸与眨眼、挥手轻晃、开心小跳、比心、吃白饭、顶铁盆、哼歌、闲置小憩；连续戳戳会切气鼓鼓。它们是本地动作，不冒充小鲸的模型回复。
- 单击互动、双击打开原生小窝、滚轮缩放；可设置安静/适中/活泼、轻柔动画、气泡开关。活泼模式会偶尔在附近散步，拖动时停止散步。
- 原生窗口内的四页设置：陪看、桌宠、声音、连接；原生入口自动连接本机，浏览器入口仍须配对。
- 真实连接状态、Feiyu 服务检测、最近观察预览。未连接平板或声音服务时明确显示未连接。

## 运行（Windows / Python 3.11+）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/setup_pet.py
.\.venv\Scripts\python.exe -m screenmate
```

已安装依赖时双击 `launch.cmd`，也可右键运行 `start.ps1`。双击桌宠打开小窝，右键菜单可以开启陪看、复制配对码、打开设置和退出。用 `python -m screenmate --open-panel` 可以同时打开原生小窝。浏览器设置页为 http://127.0.0.1:17860 。启动时暂停，手动开启后持续观察。配置保存在被 Git 忽略的 `runtime/settings.private.json`。

## 已实现

- 直接复用 [dsh-co-pet](https://github.com/LINNoot/dsh-co-pet) 的窗口、动画播放器、拖动、缩放、托盘与气泡，并接入 [dsh-pet-dafeiyu](https://github.com/bauerelizabeth07139/dsh-pet-dafeiyu) 的 Q版角色；不安装 DSH。尝试通过 Windows 显示亲和性排除桌宠和气泡截图。
- 常驻观察、1–3600 秒调频、截图区域坐标、文字/视觉/混合模式、可选重复帧跳过。
- 串行截图，不积压采集请求；最新画面只在内存保存，暂停及采集失败清除；默认 90 秒过期。
- Chromium 扩展：主动开启当前页，按频率提交可见文字，隐藏标签页停止采集，不读取输入框或 URL 查询参数。
- Bearer 鉴权的电脑端 HTTP 接口；默认仅监听本机回环地址。
- 配套 AstrBot 插件：后台拉取最新观察，图片交给已配置视觉模型，文字直接带入主人私聊；沿用已有对话人格，实际回复镜像到桌面。
- Feiyu TTS HTTP 适配：异步任务提交、状态轮询、PCM WAV 校验和 Windows 播放；新台词打断旧播放。

## 浏览器文字

在 Chrome / Edge 扩展管理页开启开发者模式，选择“加载已解压的扩展程序”，选中 `browser-extension`。在要陪看的页面打开扩展，填写桌面端配对码与文字采集间隔，点击开启。电脑端也需开启观看。

文字模式不截屏。混合模式同时截图；想节省视觉调用应明确选择文字模式。Canvas、图片、隐藏线索与跨域 iframe 不能保证通过文字读取，需切换视觉。扩展的配对码仅存浏览器会话存储，浏览器退出后重新填写。

## AstrBot 接入

将 `integrations/astrbot_plugin_xiaojing_screenmate` 文件夹复制到 AstrBot 的插件目录，安装其中 requirements。**当前未部署到你的平板，不会改动已有小鲸。** 插件配置需填写电脑地址、配对码、主人 ID，以及视觉模型提供商 ID。文字模式不需要视觉模型。模型调用使用 AstrBot 现有配置，仍可能计费。

同一电脑可以使用默认回环地址；平板需要通过受信网络访问电脑，手动运行：

```powershell
.\.venv\Scripts\python.exe -m screenmate --host 0.0.0.0
```

局域网连接需要核对电脑地址、防火墙和实际网络。当前 HTTP 不加密，仅适用于受信网络或已有加密隧道，不要向公网转发端口。配对码可控制观看并读取屏幕，不能公开。更换配对码请退出程序后删除私有配置中的 token 字段，再启动生成新码。

插件持续读取观察并调用视觉；当前只在主人正常私聊时把观察带入现有对话并镜像回复。**自主接话、桌面输入送入现有小鲸会话、共享短期对话记忆仍待下一阶段接入**，本版不创建额外的 QQ 主动消息链。

## 本地声音

先独立部署 [Feiyu Voice](https://github.com/Esmerubphire/astrbot_plugin_feiyu_voice)，再在控制页填写声音服务地址、密钥与 cute/gentle 声线。本仓只实现接口，不包含模型、训练数据或推理服务。新台词停止本机旧音频，但已提交的服务端任务可能仍会继续推理。

## 验证与边界

```powershell
.\.venv\Scripts\python.exe -m pip install pytest -r integrations/astrbot_plugin_xiaojing_screenmate/requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

回归覆盖鉴权、暂停清除、暂停期间采集竞态、过期画面、截图失败、文字模式、参数校验与慢回复。

需要实机另行验收：AstrBot 安装和模型识图、本地 Feiyu 合成音质/延迟、浏览器扩展安装和真实网页、锁屏行为、全屏游戏和多屏缩放。尚无窗口选择器、额外素材包导入界面、点击穿透、麦克风输入或自动场景选择。桌宠来源与资源边界见 [THIRD_PARTY.md](docs/THIRD_PARTY.md)。

后续设计与进度见 [docs/ROADMAP.md](docs/ROADMAP.md)。
