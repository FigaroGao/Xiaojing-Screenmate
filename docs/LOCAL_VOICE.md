# 本机 Feiyu 语音

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
