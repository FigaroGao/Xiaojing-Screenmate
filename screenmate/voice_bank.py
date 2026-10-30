"""Allowlisted local phrases; IDs never accept arbitrary paths."""
from pathlib import Path
import json

PHRASES = {
    'hm': '嗯，我在呢。',
    'here': '我在呢。',
    'watching': '我也在看。',
    'quiet': '你忙你的，我在旁边待一会儿。',
    'interesting': '这个还挺有意思的。',
    'take_time': '不着急，你慢慢来。',
    'sudden': '诶，这一下有点突然。',
    'surprise': '啊，还能这样。',
    'wait': '等等，我还没反应过来。',
    'funny': '这段有点好笑。',
    'funny_again': '再看一遍，还是好好笑。',
    'expression': '刚才那个表情，哈哈。',
    'plot_twist': '好家伙，在这儿等着呢。',
    'beautiful': '哇，这个画面好看。',
    'sea': '这片海真好看。',
    'scenery': '这个地方，看着很舒服。',
    'animal': '这个小家伙好可爱。',
    'round': '好圆啊，像个团子。',
    'food': '看着有点馋了。',
    'cooking': '这锅看起来不错。',
    'color': '这个颜色好漂亮。',
    'shot': '哇，这一枪。',
    'nice_play': '漂亮，这下打得好。',
    'steady_play': '刚才那波挺稳的。',
    'unexpected_win': '这也能赢啊。',
    'close_loss': '差一点，就差一点。',
    'pity': '这波确实可惜。',
    'tense': '有点紧张了。',
    'uncertain_match': '这局还真不好说。',
    'clue': '等等，这个可能是线索。',
    'found': '哦，原来在这里。',
    'connection': '这两个地方好像能对上。',
    'understand': '哦，这样就说得通了。',
    'detail': '刚才那个小细节，有点意思。',
    'working': '这一步，总算过去了。',
    'agree': '嗯，这个我也喜欢。',
}

CONTEXTS = {
    'sudden':'画面出现明确突发变化', 'surprise':'内容出现意外反转',
    'wait':'画面信息变化快且并非主人忙碌', 'funny':'明确搞笑片段',
    'funny_again':'确实重复看同一搞笑片段', 'expression':'明确搞笑的角色表情',
    'plot_twist':'明确剧情反转', 'beautiful':'漂亮的画面', 'sea':'画面明确是海景',
    'scenery':'自然风景', 'animal':'画面有可爱动物', 'round':'动物或物件明显圆滚滚',
    'food':'画面明确有食物', 'cooking':'画面正在做饭且能看到锅内食物', 'color':'画面色彩突出',
    'shot':'游戏里明确出现漂亮击杀', 'nice_play':'游戏里明确有精彩操作',
    'steady_play':'明确观察到稳定操作', 'unexpected_win':'确实出现意外获胜',
    'close_loss':'确实惜败且主人没有要求安静', 'pity':'游戏或比赛出现可惜失误',
    'tense':'正在看比分接近的比赛', 'uncertain_match':'比赛局势确实难料',
    'clue':'解谜画面有具体候选线索，不给答案', 'found':'明确找到之前寻找的东西',
    'connection':'具体两个线索有对应依据', 'understand':'有新信息使之前疑点得到解释',
    'detail':'画面存在具体值得注意的小细节', 'working':'明确任务完成提示，不猜主人进度',
    'agree':'主人刚明确表达了喜欢某个具体东西',
}

def catalog(root):
    folder=Path(root)/'voice-bank'
    return [{'id':ident,'text':text,'automatic':ident in CONTEXTS,'when':CONTEXTS.get(ident,'只供手动使用，不定时自动播放')}
            for ident,text in PHRASES.items() if (folder/(ident+'.wav')).is_file()]

def audio_path(root,ident):
    if ident not in PHRASES:raise ValueError('未知预存语音')
    path=Path(root)/'voice-bank'/(ident+'.wav')
    if not path.is_file() or path.is_symlink():raise ValueError('预存语音尚未生成')
    return path
