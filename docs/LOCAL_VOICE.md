# 本机 Feiyu 语音

2026-10-31：现在由小窝独立语音开关控制，每次启动默认关闭，不再随Screenmate自动加载。开启后异步加载、真实就绪才合成；可途中取消，关闭或退出卸载本机常驻进程。实际冷启动216秒，保持原FP16选择。详情与验证边界见[本次更新](UPDATE-20261031.md)。下方数据为同一声线此前的精度比较记录。

## 当前选择：FP16 优先响应速度

主人试听并比较后选择恢复 FP16：短句约4–7秒、桌面总显存约3.2GB。本机 `runtime/resident-voice.private.json` 已恢复为 `{"precision":"fp16"}`，常驻服务按该模式重启。以下 INT8 记录保留为可选省显存方案，当前不启用。

## INT8 省显存试验记录

省显存试验时私有配置为 `{"precision":"int8"}`。新增依赖 bitsandbytes==0.49.1 安装在现有 WSL 推理环境，不升级 Torch；采用官方 [Linear8bitLt](https://huggingface.co/docs/bitsandbytes/reference/nn/linear8bit) 路径（has_fp16_weights=False、threshold=6）。只量化 Qwen transformer layers 的168个 Linear，并逐层验证权重确实为 torch.int8；嵌入、语音输出头、声学模型仍为 FP16，波形解码器 FP32。capabilities 中的 parameter_dtypes 是各大模块第一个参数的类型，llm 显示 float16 指的是保留的嵌入；quantized_layers=168 才是内部 INT8 层的数量。

与FP16相同三句测试：16.016/11.594/12.718秒，音频4.44/3.68/4.44秒；同一进程连续成功。INT8 PyTorch allocated稳态1386MiB、reserved1522MiB，FP16为1733/1864MiB：allocated减少347MiB，reserved减少342MiB。桌面总显存快照2784MiB，FP16先前为3280MiB；总量受其他应用影响，不能全部归因于量化。

采用 INT8 的取舍是短句生成明显慢于FP16（约12–16秒对比4–7秒），仅用于显存优先模式。三段PCM均非静音、无削波，原始模型文件未改写；人工音质满意度和游戏并行仍需体验。切回私有配置中的 fp16 并重启常驻服务即可恢复之前模式；不要只改文件而期待已加载模型即时转换。

重建环境时需在 WSL 推理 venv 安装 `bitsandbytes==0.49.1`，可用 `--no-deps` 保留锁定的 Torch 环境，并运行 pip check 和实际 CUDA/语音验收。

## FP16 实测与本机选择

本机已在 `runtime/resident-voice.private.json` 保存 `{"precision":"fp16"}`。启动器将选择传给常驻服务；没有此私有设置时默认为 fp32。改成 fp32 后需重新启动常驻进程才能回退，改变文件不会修改已加载的模型。

这是 Screenmate 常驻适配器的额外精度选项，不改写上游模型文件、源码、官方运行时 profile 或诊断结果。使用上游 fp16 自动混合精度路径，并将 llm/flow 参数显式转为 float16；最终波形解码器 hift 保留 float32。

三句相同测试请求：FP32 耗时6.969/4.531/4.735秒；FP16 耗时6.672/3.937/4.344秒，输出4.44/3.80/4.44秒。FP16 第一句与第三句文字相同，结果可重复；自回归模型精度变化会改变采样结果，不能以波形逐样本相等作为音质标准。

前后桌面总显存快照4874/3280MiB，包含其他应用，不是单独模型显存的严格受控对照。FP16服务报告 PyTorch allocated 1724–1733MiB、reserved 1862–1864MiB；这些数值不包含全部 ONNX/CUDA/其他进程占用。此次冷加载151.9秒，受缓存状态影响，不能归因于半精度速度提升。

三段24kHz PCM输出通过有限值、非静音和无削波检查（RMS约0.073–0.080，削波样本0），桌面实际播放及PCM嘴型再次通过。人工音质盲听、长文本稳定性和大型游戏并行尚未验收。原 FP32 输出与 FP16 输出均保留在本机 runtime/previews 供对比。

## 当前默认：可爱模型常驻

Screenmate 使用 `tools/resident_voice.py` 在 WSL 中提供仅回环监听的 `127.0.0.1:9881`。启动时校验原始模型与源码摘要、加载可爱 checkpoint、验证 CUDA 设备，并通过上游 `add_zero_shot_spk` 缓存参考音频特征。后续任务复用同一个模型、缓存与 CUDA 上下文；每次检查已验证文件的大小/修改时间，检测变化则拒绝合成，需重启重新校验。不修改上游源码、权重和校验清单。

服务保留 Bearer 鉴权，只接受 cute，串行合成，队列上限4；最多保留16个任务的音频于内存，不把新台词和输出写入磁盘。已提交任务不提供服务端取消。退出 Screenmate 后服务仍常驻，便于再次打开时复用；结束常驻 Python 进程才会释放其显存。重新启动服务需再次冷加载。

本机连续三句实测总耗时6.969/4.531/4.735秒，输出时长3.92/3.96/3.92秒，三个任务的服务PID相同。首次进程初始化214.1秒。经 Screenmate 实际试听，Windows播放和 PCM 嘴型变化再次验证通过；系统总显存占用约5.0GB/6GB（包含其他桌面应用），未验收大型游戏并行。

首次连接运行 `tools/connect_local_voice.py`；已配好时启动 Screenmate 自动拉起或复用服务。原始隔离服务9880作为回退，使用 `tools/connect_local_voice.py --isolated`。以下旧服务记录与历史计时保留用于对比，当前默认不再逐句冷加载。

模型和服务来自 [Esmerubphire/astrbot_plugin_feiyu_voice](https://github.com/Esmerubphire/astrbot_plugin_feiyu_voice)，服务源码固定 `76774b499f7d306454562d56348dd63399b6d7e8`。使用已训练好的可爱/温柔声线进行本地推理，不涉及重新训练。

## 安装位置

- Windows API：`runtime/feiyu-voice/server/.venv`，只监听 `127.0.0.1:9880`。
- 模型：`runtime/feiyu-voice/server/models/FeiyuVoice-CosyVoice3`。
- WSL Ubuntu-22.04 CUDA 推理：`runtime/voice-linux/tts`，NVIDIA RTX 3060 Laptop GPU。
- Linux Python、下载缓存和推理环境均在 E 盘，WSL 系统只补充 FFmpeg/libsox。
- 配置：服务内 `configs/voice_service.json`、`configs/runtime.tts.cuda.local.json`；API key 只存服务的 `.runtime/voice-service/api_key.txt` 与 Screenmate 私有设置。

模型快照为 `f37e9d1dda26e8b45b4e9f1b4c347c0a07b797e2`，36个文件，共7,452,796,369字节。下载工具 `tools/download_feiyu.py` 校验 Hugging Face LFS 摘要和包内公开 SHA256 清单；不改写校验文件。模型与环境不进入 Git。

CosyVoice 代码固定 `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc`，使用上游 CUDA preset 和源码摘要校验，FP32、CPU ONNX。`runtime/voice-linux/tts/diagnostic.json` 记录实际 GPU 内核与导入检查；只有真实语音任务成功才算合成验收。

## 使用

双击项目的 `launch.cmd`。已连接此安装的 Screenmate 会自动启动本机 API 服务，在“小鲸的声音”选择声线并点“试听当前声线”。真实回复也走同一条合成、播放、PCM 嘴型同步链路。切换声线无需重新下载模型。

API 服务串行处理任务；每次任务需要检查模型并冷加载，初次生成会慢于播放时长。停止本机播放不会取消已提交的 GPU 任务。现有播放使用 Windows 默认音频设备。

重新接线可运行 `.venv\Scripts\python.exe tools/connect_local_voice.py`，前提是官方运行时诊断已经通过且 Screenmate 已启动。它不会输出密钥。

当前只安装说话所需的 TTS，未安装唱歌、翻唱或新声线训练环境。平板 AstrBot 桥接仍需单独部署；本机语音成功不表示平板已连接。
## 本机验收记录

2026-10-30：官方运行时诊断通过 RTX 3060 Laptop CUDA 的 matmul/conv1d/FFT 与导入检查；pip check 通过。两种声线均通过真实 HTTP 任务生成有效 24kHz WAV。同一句普通中文：cute 输出3.92秒、耗时252.2秒；gentle 输出5.44秒、耗时396.4秒。这是当前机器的单次实测，不能当作实时速度保证。

当前 WSL 环境与权重放在 Windows E 盘，加上每个任务冷加载，生成延迟很高；即时陪聊还需要后续优化常驻推理和存储访问。实测推理时显存约4.3GB（包含桌面其他占用），未测试与大型游戏同时运行。

文字规范化组件的 ModelScope 资源请求返回403，CosyVoice 自动使用基础文本回退；普通中文测试成功，数字/日期等朗读规范化尚未验收。

桌面试听链路已通过：设置页接口提交后由 FeiyuVoice 实际合成并经 Windows 播放，状态轮询观察到 speaking 为真且 PCM mouth 幅度大于阈值，播放结束恢复静音。
## 可爱声线与延迟定位（2026-10-30）

按主人偏好，Screenmate 固定 cute：移除温柔选项，设置接口拒绝 gentle，旧配置启动时迁移为 cute；模型原文件保留。

独立计时：完整7GB模型摘要校验35.338秒、源码校验3.081秒、import torch 14.689秒、import CosyVoice 32.180秒，共约85秒，尚未开始加载权重。原任务记录中可爱语音3.92秒的上游推理阶段约6.22–7.39秒（speech seconds × RTF）；运行时记录的模型加载到输出阶段为98.78–122.25秒。不同任务、不同缓存状态的测量不能直接相加解释单次总耗时。

服务 jobs.py 为每个任务启动子进程，worker 经 WSL 再启动推理程序，tts.py 每次重校验整个模型并创建 AutoModel；可爱声线还在基础权重加载后装载可爱 checkpoint。当前跨 Windows/WSL 的 E盘文件访问及每次重复初始化是主要开销，ModelScope 的403是另一个启动问题；实际神经网络推理并非持续数分钟。

优先优化方向是常驻可爱模型、复用参考音频特征、把完整性校验放到受控初始化并检测文件变更，以及改善 WSL 文件访问。尚未实施这些架构优化，不能宣称已降低实际合成延迟。
