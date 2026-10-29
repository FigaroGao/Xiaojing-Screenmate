# Coopanion 动态桌宠调研 / 2026-10-30

来源：https://github.com/Pal-AI-Lab/Coopanion

本次查看 revision：`494a82c95c8fe833bf07b8bf61947f52ae4ec4c0`。源码仅保存在被 Git 忽略的 `runtime/candidates/Coopanion`，没有替换当前桌宠，也没有安装完整 Coopanion 或迁移小鲸人格/记忆。

## 与当前桌宠的区别

当前 v0.2 使用18种现成姿态，通过眨眼、嘴型切换、整体缩放/轻晃和窗口位移增加动态。Coopanion 的鲸鱼娘是二头身分层模型：贴图铺在网格上，经 WebGL 变形器逐帧绘制；后发、刘海、裙摆、尾巴、鲸鳍、呆毛和手臂有独立弹簧，视线、眼睑、嘴型和表情分别更新。更适合连续互动与自然过渡。

相关文件：

- `packages/cortico-world-desktop-pet/web/whale/figure.js`：鲸鱼娘模型与动态参数。
- `web/whale/model.json`：部件、枢轴与贴图位置。
- `web/kit/rig.js`：网格变形与 WebGL 绘制。
- `web/kit/body.js`：行为、走路、坐下、拖拽、说话与表情。
- `web/figure-frame.js`：形象托管协议。
- `examples/whale/`：独立演示，不依赖整个 Cortico 应用启动。

## 本机验证

在桌宠包目录运行 `node examples/whale/serve.mjs 17862`，演示地址为 `http://127.0.0.1:17862/examples/whale/`。

演示脚本已检查，仅在127.0.0.1提供静态文件。网页实际载入鲸鱼娘、表情和动作按钮，放大至1.6，操作了招手、站起和自由活动开关，实际窗口可见连续动画。演示未连接模型、QQ或Feiyu，也不代表已接入Screenmate。画面上的帧率数字不作为实际桌面性能保证。

## 接入方向

优先试接图形层：通过已有 Qt WebEngine 承载形象，保持当前Python采集与鉴权服务、原生小窝、AstrBot桥接和Feiyu客户端。用实际观察/对话/音频状态驱动形象，不接入官方演示的随机台词，不另建小鲸人格或记忆。

需要另行验证透明窗口、鼠标命中/穿透、多屏拖拽、截图排除、WebGL兼容性、资源占用和真实音频嘴型同步。当前v0.2保留，替换前先做可切换的图形原型。

## 源码与贴图声明

当前主仓库和桌宠包声明 `AGPL-3.0-or-later`。`packages/cortico-world-desktop-pet/THIRD_PARTY_NOTICES.md` 明确鲸鱼娘贴图不在本包AGPL授权范围内，另行列出原设、参考与商标来源；不能把早期版本的MIT声明套用到本次查看版本。这里只记录来源声明，未重新发布第三方代码或贴图。
