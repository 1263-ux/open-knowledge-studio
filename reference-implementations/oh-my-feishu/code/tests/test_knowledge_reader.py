import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "cli"))

from feishu_worker.config import WorkerConfig
from feishu_worker.knowledge_reader import KnowledgeReader, DISPLAY_FIELDS, snapshot_record
from feishu_worker.knowledge_reader import _read_only_json, merge_observation
from knowledge_studio import worker_records


def config(tmp_path):
    return WorkerConfig('secret-token','tbl1',Path('/fake/lark'),tmp_path)


def test_optional_transport_vocabulary_matches_packaged_core():
    assert DISPLAY_FIELDS == worker_records.DISPLAY_FIELDS


def test_paginated_reader_calls_only_read_operations_and_preserves_partial(tmp_path):
    calls=[]
    def call(config,*args,root):
        calls.append(args)
        if args[1]=='+field-list':
            return {'data':{'fields':[{'name':name} for name in DISPLAY_FIELDS]}}
        assert args[1]=='+record-list'
        offset=int(args[args.index('--offset')+1])
        rows=[{'record_id':'r1','fields':{'质量状态':'partial','知识域':['science','computing']}},{'record_id':'r2','fields':{'质量状态':'failed'}}] if offset==0 else [{'record_id':'r3','fields':{'质量状态':'skipped'}}]
        return {'data':{'data':rows,'total':3,'has_more':offset==0}}
    reader=KnowledgeReader(config(tmp_path),tmp_path,call=call,ttl=60)
    result=reader.snapshot()
    assert result['state']=='live' and len(result['records'])==3 and not result['partial']
    assert [r['fields']['质量状态'] for r in result['records']]==['partial','failed','skipped']
    assert 'secret-token' not in json.dumps(result)
    assert len(calls)==3
    assert reader.snapshot() is result and len(calls)==3
    assert all(args[1] in {'+field-list','+record-list'} for args in calls)


def test_read_failure_preserves_success_time_and_marks_stale(tmp_path):
    fail=False
    def call(config,*args,root):
        if fail:
            raise RuntimeError('secret-token must not escape')
        return {'data':{'fields':[{'name':'评级'}]}} if args[1]=='+field-list' else {'data':{'data':[{'record_id':'r','fields':{'评级':'A'}}],'has_more':False}}
    reader=KnowledgeReader(config(tmp_path),tmp_path,call=call)
    first=reader.snapshot()
    fail=True
    result=reader.snapshot(force=True)
    assert result['state']=='stale'
    assert result['records']==first['records']
    assert result['observed_at']==first['observed_at']
    assert 'secret-token' not in json.dumps(result)
    missing=KnowledgeReader(config(tmp_path),tmp_path,call=call).snapshot()
    assert missing['state']=='error' and missing['records']==[]


def test_source_snapshot_never_copies_tokens_or_control_fields(tmp_path):
    result=snapshot_record(config(tmp_path),'r',{'知识域':['computing'],'租约所有者':'PRIVATE','base_token':'SECRET'})
    assert result['fields']=={'知识域':['computing']}
    assert result['source']['record_id']=='r'
    assert 'SECRET' not in json.dumps(result) and 'secret-token' not in json.dumps(result)


def test_record_cap_is_explicitly_partial(tmp_path):
    def call(config,*args,root):
        if args[1]=='+field-list': return {'data':{'fields':[{'name':'评级'}]}}
        return {'data':{'data':[{'record_id':'a','fields':{}},{'record_id':'b','fields':{}}],'has_more':True}}
    result=KnowledgeReader(config(tmp_path),tmp_path,call=call,max_records=2).snapshot()
    assert result['partial'] and len(result['records'])==2


def test_transport_forbids_mutation_and_has_a_bounded_subprocess(monkeypatch,tmp_path):
    from types import SimpleNamespace
    calls=[]
    def run(args,**kwargs):
        calls.append((args,kwargs))
        return SimpleNamespace(returncode=0,stdout='{"ok":true,"data":{}}')
    monkeypatch.setattr('feishu_worker.knowledge_reader.subprocess.run',run)
    with pytest.raises(ValueError):
        _read_only_json(config(tmp_path),'base','+record-update',root=tmp_path)
    assert not calls
    assert _read_only_json(config(tmp_path),'base','+record-list',root=tmp_path)['ok']
    assert calls[0][1]['timeout']==10
    assert isinstance(calls[0][0],list) and 'shell' not in calls[0][1]


def test_new_observation_preserves_other_sources_and_missing_fields(tmp_path):
    old=snapshot_record(config(tmp_path),'r1',{'评级':'B','质量状态':'partial'})
    other=snapshot_record(config(tmp_path),'r2',{'知识域':['science']})
    current=snapshot_record(config(tmp_path),'r1',{'评级':'A'})
    result=merge_observation([old,other],current)
    assert len(result)==2
    assert result[0]['fields']=={'评级':'A','质量状态':'partial'}
    assert result[1]==other
    assert old['fields']['评级']=='B'
