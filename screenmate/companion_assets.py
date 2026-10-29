"""Load existing chibi artwork into the existing desktop pet renderer.

No generated illustrations, no changes to upstream source or original images.
The small breathing frames are runtime transforms of the supplied artwork.
"""
import math
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
CHIBI_REVISION = "fc1ad4c0fa29ee29338a469c74ebe7776bf3d66a"
SPRITES = ROOT / "runtime/chibi-dafeiyu/assets/sprites"
POSES = {
    "idle": "待机", "blink": "眨眼", "walk1": "迈步", "walkpass": "轻快走路", "walk2": "走路",
    "happy": "开心", "cheer": "欢呼", "talk": "说话", "think": "思考", "love": "比心",
    "sad": "委屈", "angry": "气鼓鼓", "surprise": "惊讶", "sleep": "小憩", "wave": "挥手",
    "sing": "哼歌", "basin": "顶铁盆", "eat": "吃白饭",
}


def load_companion(pet_type):
    images = {}
    for pose in POSES:
        path = SPRITES / f"dafeiyu-{pose}.png"
        if not path.is_file():
            raise RuntimeError("Q版素材尚未安装，请运行 python tools/setup_pet.py")
        with Image.open(path) as image:
            images[pose] = image.convert("RGBA").resize((218, 269), Image.Resampling.LANCZOS)
    # Keep the supplied 503 x 620 layout. Never trim each pose independently:
    # that makes feet and the face jump when the expression changes.
    size = images["idle"].size
    # Upstream manifest marks idle/blink as left-facing; all other poses face right.
    for pose in ("idle", "blink"):
        images[pose] = ImageOps.mirror(images[pose])

    def breath(pose, count=24, blink=False):
        result = []
        for i in range(count):
            image = images["blink"] if blink and i in (26, 27) else images[pose]
            amount = (1 + math.sin(2 * math.pi * i / count)) / 2
            height = size[1] - round(amount * 2)
            frame = Image.new("RGBA", size)
            scaled = image.resize((size[0], height), Image.Resampling.LANCZOS)
            phase = 2 * math.pi * i / count
            tilt = {"wave": 2.2, "love": 1.4, "eat": .9, "angry": 2.5, "sing": 2.0}.get(pose, 0)
            if tilt:
                scaled = scaled.rotate(math.sin(phase) * tilt, Image.Resampling.BICUBIC,
                                       center=(size[0] / 2, height * .9))
            hop = round(max(0, math.sin(phase)) * {"cheer": 10, "happy": 4, "surprise": 3}.get(pose, 0))
            frame.alpha_composite(scaled, (0, size[1] - height - hop))
            result.append(frame)
        return result

    frames = {pose: breath(pose) for pose in POSES}
    frames["idle"] = breath("idle", 48, blink=True)
    frames["talk"] = [images[p] for p in ("talk", "talk", "talk", "idle", "idle", "talk", "talk", "talk", "blink", "idle")]
    walk = [images[p] for p in ("walk1", "walkpass", "walk2", "walkpass")]
    frames.update({"running-right": walk, "running-left": [ImageOps.mirror(im) for im in walk],
                   "waving": frames["wave"], "jumping": frames["cheer"],
                   "failed": frames["sad"], "waiting": frames["idle"],
                   "running": frames["talk"],
                   "review": frames["think"]})
    return pet_type(name="xiaojing-chibi", display_name="小鲸 · Q版", description="大肥鱼 Q版 18 姿态",
                    path=SPRITES, sheet_path=SPRITES / "dafeiyu-idle.png", meta={},
                    sprite_version_number=0, cell_w=218, cell_h=269, rows=list(frames), frames=frames)
