"""Pinned upstream assets and the supported desktop renderer contract."""
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/coopanion"
REVISION = "494a82c95c8fe833bf07b8bf61947f52ae4ec4c0"
WEB = SOURCE / "packages/cortico-world-desktop-pet/web"
SCHEMES = ("deepseek", "harness", "chatgpt", "claude", "gemini", "qwen", "kimi", "minimax")
OUTFITS = ("maid", "cape", "crew")
ACTIONS = {
    "neutral": "平静", "happy": "开心", "wink": "眨眼", "love": "喜欢", "shy": "害羞",
    "surprised": "惊讶", "angry": "生气", "sad": "难过", "sleepy": "犯困", "thinking": "思考",
    "smug": "得意", "pout": "嘟嘴", "worried": "担心", "determined": "认真", "flustered": "慌张",
    "scared": "害怕", "excited": "期待", "cry": "大哭", "confused": "疑惑", "stand": "站起",
    "jump": "跳跃", "hop": "小跳", "look": "张望", "turn": "转身", "nod": "点头",
    "shake": "摇头", "spin": "转圈", "sit": "坐下", "sleep": "睡觉", "dizzy": "晕乎",
    "walk": "散步", "run": "跑步", "wave": "招手", "bow": "鞠躬", "shiver": "发抖",
    "flap": "扑腾", "dance": "跳舞",
}


def asset_path(relative):
    """Only expose rendering code and graphics under the pinned web directory."""
    relative = unquote(relative)
    if "\\" in relative or "\x00" in relative or any(p in ("..", ".") for p in relative.split("/")):
        return None
    path = (WEB / relative).resolve()
    if not path.is_relative_to(WEB.resolve()) or path.suffix not in (".js", ".json", ".png", ".webp", ".svg", ".css"):
        return None
    return path if path.is_file() else None


def hit_test(layout, x, y):
    """Renderer hit circles use Qt logical pixels, including on scaled displays."""
    for circle in layout.get("hit", []):
        if (x-circle["x"])**2 + (y-circle["y"])**2 <= circle["r"]**2:
            return True
    bubble = layout.get("bubbleRect")
    return bool(bubble and bubble["x"] <= x <= bubble["x"]+bubble["w"] and bubble["y"] <= y <= bubble["y"]+bubble["h"])


def transfer_delta(old_origin, new_origin):
    return old_origin[0]-new_origin[0], old_origin[1]-new_origin[1]
