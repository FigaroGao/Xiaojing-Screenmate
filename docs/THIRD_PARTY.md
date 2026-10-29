# 桌宠复用说明

桌宠窗口、动画播放器、气泡、托盘和角色选择直接复用 [LINNoot/dsh-co-pet](https://github.com/LINNoot/dsh-co-pet)，固定 revision `b394cdacca07526a36a36373cb11bec603b74651`。不要求安装 DSH；本项目直接实例化现有 PetWidget，仅增加 Screenmate 菜单和状态适配，不重写渲染。

上游代码采用 MIT，版权为 `Copyright (c) 2026 dsh-pet contributors`。完整许可随下载的上游仓库保留。依赖下载到被 Git 忽略的 runtime/dsh-co-pet，不随本仓重新分发代码或图片。

上游自带 deepseek 和 yuexinmiao 宠物包。图片的独立授权须参照上游来源说明，不能把 MIT 代码许可当作图片许可；后续公开发布或打包前应逐项核验。本次仅在用户电脑保留上游原始包用于本机接入。

最初的自绘占位桌宠已按用户要求移除。

## v0.2 / Q版角色

Q版 18 姿态直接读取 [bauerelizabeth07139/dsh-pet-dafeiyu](https://github.com/bauerelizabeth07139/dsh-pet-dafeiyu) 的 `assets/sprites/`，固定 revision `fc1ad4c0fa29ee29338a469c74ebe7776bf3d66a`。上游仓库声明 MIT，版权 `Copyright (c) 2026 bauerelizabeth07139`，完整许可与素材 manifest 随下载仓库保留。

本项目不使用上游的预录语音、固定女儿人格或父女联动剧情；只读取现有图片，运行时做呼吸、轻晃、眨眼和姿态映射。原始图片不改写。图片和上游源代码都留在被忽略的 runtime，GitHub 记录我们的适配器与固定依赖版本。以后公开分发角色图片或打包时仍须核对角色原设、商标与上游素材的完整来源链。
