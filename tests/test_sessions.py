from screenmate.core import Engine
from screenmate.sessions import Sessions
import importlib.util
from pathlib import Path

def test_repeated_enable_does_not_split_and_pause_queues_once(tmp_path):
    e=Engine(tmp_path);e.set_enabled(True)
    ident=e.sessions.current
    e.set_enabled(True)
    assert e.sessions.current==ident
    job=e.submit_chat('一起看')
    assert e.take_chat()['episode_id']==ident
    e.set_enabled(False);e.set_enabled(False)
    pending=e.sessions.pending()
    assert len(pending)==1 and pending[0]['ended']>=pending[0]['started']
    e.sessions.acknowledge(ident,42)
    assert not e.sessions.pending()

def test_abrupt_exit_ends_at_last_seen_not_restart(tmp_path):
    s=Sessions(tmp_path/'times.sqlite3');s.start();s.touch()
    recovered=Sessions(s.path).pending()
    assert recovered[0]['reason']=='interrupted'
    assert recovered[0]['ended']==recovered[0]['last_seen']

def test_watch_memory_keeps_raw_separate_and_records_write_intent(tmp_path):
    path=Path(__file__).parents[1]/'integrations/astrbot_plugin_xiaojing_screenmate/watch_memory.py'
    spec=importlib.util.spec_from_file_location('watch_memory_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    s=module.WatchMemory(tmp_path/'memory.sqlite3')
    s.note('one','a','第一场');s.note('two','a','第二场');s.note('one','a','重复')
    assert s.material('one')==('第一场',1,1)
    s.save_draft('one','总结');s.save_draft('one','不应覆盖')
    s.state('one','writing')
    assert s.summary('one')==('总结','writing',None)
    s.state('one','stored',42)
    assert s.summary('one')[2]==42
