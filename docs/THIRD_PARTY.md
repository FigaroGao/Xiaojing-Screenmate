# 桌宠复用说明

桌宠窗口、动画播放器、气泡、托盘和角色选择直接复用 [LINNoot/dsh-co-pet](https://github.com/LINNoot/dsh-co-pet)，固定 revision `b394cdacca07526a36a36373cb11bec603b74651`。不要求安装 DSH；本项目直接实例化现有 PetWidget，仅增加 Screenmate 菜单和状态适配，不重写渲染。

上游代码采用 MIT，版权为 `Copyright (c) 2026 dsh-pet contributors`。完整许可随下载的上游仓库保留。依赖下载到被 Git 忽略的 runtime/dsh-co-pet，不随本仓重新分发代码或图片。

上游自带 deepseek 和 yuexinmiao 宠物包。图片的独立授权须参照上游来源说明，不能把 MIT 代码许可当作图片许可；后续公开发布或打包前应逐项核验。本次仅在用户电脑保留上游原始包用于本机接入。

最初的自绘占位桌宠已按用户要求移除。
