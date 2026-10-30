"""Tracked renderer commands; queue acceptance is never a completion receipt."""
import secrets,time,math

TARGETS={'top_left','top_right','bottom_left','bottom_right','left','right','top','bottom','coordinates','app'}
TERMINAL={'completed','rejected','interrupted','cancelled','timeout'}

class PetCommands:
    def __init__(self):self.records={}
    def create(self,kind,**payload):
        ident=secrets.token_hex(12)
        self.records[ident]={'id':ident,'kind':kind,'state':'queued','created':time.time(),**payload}
        # Never evict an in-flight command; completed history is bounded.
        for key in list(self.records):
            if len(self.records)<=128:break
            if self.records[key]['state'] in TERMINAL:self.records.pop(key)
        return dict(self.records[ident])
    def feedback(self,ident,state,reason='',**extra):
        row=self.records.get(ident)
        if not row or row['state'] in TERMINAL:return
        if state not in TERMINAL|{'started'}:raise ValueError('invalid renderer state')
        if state=='completed' and row['state']!='started':raise ValueError('completion requires start')
        row.update(state=state,reason=str(reason)[:200],updated=time.time(),**extra)
    def get(self,ident):
        row=self.records.get(ident)
        if not row:raise ValueError('动作编号不存在或已过期')
        if row['state'] not in TERMINAL and time.time()-row['created']>75:
            self.feedback(ident,'timeout','renderer did not confirm completion')
        return dict(row)
    def cancel(self):
        for ident in self.records:self.feedback(ident,'cancelled','watching paused or configuration changed')

def validate_move(target,x,y,app,side):
    if target not in TARGETS or side not in ('left','right','above','below'):raise ValueError('未知移动目标')
    if target=='coordinates':
        if any(type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=1 for n in (x,y)):
            raise ValueError('坐标必须是0至1的有限数字')
    if target=='app' and (not isinstance(app,str) or not 1<=len(app.strip())<=120):raise ValueError('需要准确程序名称')
