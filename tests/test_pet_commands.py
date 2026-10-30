import time
import pytest
from screenmate.core import Engine
from screenmate.pet_commands import PetCommands

def test_command_requires_start_and_cannot_complete_after_pause(tmp_path):
    e=Engine(tmp_path);e.set_enabled(True)
    ident=e.pet_action('wave')
    assert e.pet_feedback.get(ident)['state']=='queued'
    with pytest.raises(ValueError):e.pet_feedback.feedback(ident,'completed')
    e.pet_feedback.feedback(ident,'started')
    e.set_enabled(False)
    e.pet_feedback.feedback(ident,'completed')
    assert e.pet_feedback.get(ident)['state']=='cancelled' and not e.pet_commands

def test_actual_feedback_completes_and_missing_renderer_times_out():
    store=PetCommands();first=store.create('action',pose='wave')['id']
    store.feedback(first,'started');store.feedback(first,'completed')
    assert store.get(first)['state']=='completed'
    ident=store.create('move',target='left')['id']
    store.records[ident]['created']=time.time()-80
    assert store.get(ident)['state']=='timeout'

def test_move_validation_and_no_silent_queue_eviction(tmp_path):
    e=Engine(tmp_path)
    with pytest.raises(ValueError):e.pet_move('left')
    e.set_enabled(True)
    with pytest.raises(ValueError):e.pet_move('coordinates',float('nan'),.5)
    with pytest.raises(ValueError):e.pet_move('coordinates',-1,.5)
    with pytest.raises(ValueError):e.pet_move('app',app='')
    for _ in range(16):e.pet_move('bottom_left')
    with pytest.raises(ValueError):e.pet_move('right')
    assert len(e.pet_commands)==16

@pytest.mark.parametrize('monitor,expected_state',[('display','queued'),('other','rejected')])
def test_application_target_uses_actual_window_and_rejects_other_screen(tmp_path,monitor,expected_state):
    import types,json
    from screenmate.pet import Pet
    e=Engine(tmp_path);e.set_enabled(True)
    ident=e.pet_move('app',app='chrome.exe',side='left')
    command=e.pet_commands.popleft()
    e.desktop_info=lambda:{'windows':[{'app':'chrome.exe','minimized':False,'foreground':True,'monitor':monitor,'relative_rect':[.3,.1,.8,.9]}]}
    sent=[]
    pet=types.SimpleNamespace(engine=e,screen=types.SimpleNamespace(name=lambda:'display'),
                              widget=types.SimpleNamespace(isVisible=lambda:True),
                              bridge=types.SimpleNamespace(command=types.SimpleNamespace(emit=sent.append)))
    Pet.dispatch_command(pet,command)
    assert e.pet_feedback.get(ident)['state']==expected_state
    if monitor=='display':
        payload=json.loads(sent[0]);assert payload['target']=='coordinates' and payload['x']<.3
    else:assert not sent
