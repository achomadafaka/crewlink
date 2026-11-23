"""Active crew delivery uses the existing app-server, never the next-turn queue."""
import asyncio
import json
import sys
from pathlib import Path

import pytest
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'crewlink'))
import crew_session_bridge as cb


async def exercise(tmp_path, *, active=True, reject_once=False, lost=False, wrong=False, unloaded=False, internal=False, malformed=None, silent=False, alias=False, public_target=False, silent_read=False):
    path=tmp_path/'app.sock'; calls=[]; state={'active':active,'rejected':False}
    if alias:
        target=tmp_path/'daemon';target.mkdir(mode=0o700)
        if public_target:target.chmod(0o777)
        path=target/'actual.sock'
    async def serve(ws):
        try:
            async for raw in ws:
                req=json.loads(raw);m=req['method'];calls.append(req)
                if m=='initialized':continue
                if m=='thread/read' and silent_read:await asyncio.sleep(.2)
                result={}
                if m=='thread/read':result={'thread':{'id':'thread-1','status':{'type':'notLoaded' if unloaded else 'active' if active else 'idle'}}}
                if m=='thread/turns/list':result={'data':[{'id':'turn-1','status':'inProgress' if state['active'] else 'completed'}]}
                if m=='thread/read' and malformed=='wrong_thread':result['thread']['id']='someone-else'
                if m=='thread/turns/list' and malformed=='bad_page':result['data']='unknown'
                if m=='thread/turns/list' and malformed=='bad_status':result['data'][0]['status']='mystery'
                if m in ('turn/steer','turn/start'):
                    if silent:await asyncio.sleep(.2)
                    if reject_once and not state['rejected']:
                        state.update(active=not active,rejected=True)
                        await ws.send(json.dumps({'id':req['id'],'error':{'code':-32600,'message':'turn changed'}}));continue
                    if internal:
                        await ws.send(json.dumps({'id':req['id'],'error':{'code':-32603,'message':'internal failure'}}));continue
                    if lost:
                        await ws.close();return
                    result={'turnId':'wrong' if wrong else 'turn-1'} if m=='turn/steer' else {'turn':{'id':'turn-2','status':'inProgress'}}
                    if m=='turn/start' and malformed in ('null_turn','list_turn','text_turn'):
                        result['turn']={'null_turn':None,'list_turn':[],'text_turn':'bad'}[malformed]
                await ws.send(json.dumps({'method':'thread/status/changed','params':{}}))
                await ws.send(json.dumps({'id':req['id'],'result':result}))
        except websockets.ConnectionClosed:pass
    async with websockets.unix_serve(serve,str(path)):
        connect_path=path
        if alias:
            connect_path=tmp_path/'control.sock';connect_path.symlink_to(path)
        try:
            result=await cb.codex_live('thread-1','proof-only crew message','message-1',socket_path=connect_path)
            return result,calls
        except cb.BridgeError as exc:
            return exc,calls


@pytest.mark.parametrize('active,expected',[(True,'codex_steered'),(False,'codex_started')])
def test_active_steers_idle_starts_without_queue(tmp_path,active,expected):
    result,calls=asyncio.run(exercise(tmp_path,active=active))
    assert result==expected
    methods=[r['method'] for r in calls]
    assert not any('queue' in m for m in methods)
    request=next(r for r in calls if r['method'].startswith('turn/'))
    assert request['params']['clientUserMessageId']=='message-1'
    assert request['params']['input']==[{'type':'text','text':'proof-only crew message'}]
    if active:assert request['params']['expectedTurnId']=='turn-1'
    assert not {'model','approvalPolicy','sandboxPolicy','cwd'} & request['params'].keys()


@pytest.mark.parametrize('active',[True,False])
def test_definite_turn_change_rechecks_once_without_duplicate(tmp_path,active):
    result,calls=asyncio.run(exercise(tmp_path,active=active,reject_once=True))
    assert result==('codex_started' if active else 'codex_steered')
    assert len([r for r in calls if r['method'].startswith('turn/')])==2


@pytest.mark.parametrize('change',[{'lost':True},{'wrong':True},{'internal':True}])
def test_uncertain_mutation_never_falls_back_or_resends(tmp_path,change):
    result,calls=asyncio.run(exercise(tmp_path,**change))
    assert isinstance(result,cb.BridgeError) and result.ambiguous
    assert len([r for r in calls if r['method'].startswith('turn/')])==1
    assert not any('queue' in r['method'] for r in calls)


def test_unloaded_thread_is_resumed_without_settings_override(tmp_path):
    result,calls=asyncio.run(exercise(tmp_path,active=False,unloaded=True))
    assert result=='codex_started'
    assert next(r['params'] for r in calls if r['method']=='thread/resume')=={'threadId':'thread-1'}


@pytest.mark.parametrize('malformed',['wrong_thread','bad_page','bad_status'])
def test_unknown_read_state_refuses_before_any_delivery(tmp_path,malformed):
    result,calls=asyncio.run(exercise(tmp_path,malformed=malformed))
    assert isinstance(result,cb.BridgeError) and not result.ambiguous
    assert not any(r['method'].startswith('turn/') for r in calls)


def test_response_timeout_is_unknown_and_never_queued(tmp_path,monkeypatch):
    monkeypatch.setattr(cb,'TIMEOUT',.05)
    result,calls=asyncio.run(exercise(tmp_path,silent=True))
    assert isinstance(result,cb.BridgeError) and result.ambiguous
    assert len([r for r in calls if r['method'].startswith('turn/')])==1


@pytest.mark.parametrize('malformed',['null_turn','list_turn','text_turn'])
def test_malformed_idle_ack_stays_unknown_without_unhandled_exception(tmp_path,malformed):
    result,calls=asyncio.run(exercise(tmp_path,active=False,malformed=malformed))
    assert isinstance(result,cb.BridgeError) and result.ambiguous
    assert len([r for r in calls if r['method'].startswith('turn/')])==1


def test_daemon_control_symlink_resolves_into_private_socket_directory(tmp_path):
    result,calls=asyncio.run(exercise(tmp_path,alias=True))
    assert result=='codex_steered'
    assert len([r for r in calls if r['method']=='turn/steer'])==1


def test_daemon_control_symlink_never_relaxes_target_directory_permissions(tmp_path):
    result,calls=asyncio.run(exercise(tmp_path,alias=True,public_target=True))
    assert isinstance(result,cb.BridgeError) and not result.ambiguous
    assert not calls


def test_loaded_thread_read_timeout_names_daemon_stall(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, 'TIMEOUT', .05)
    result, calls = asyncio.run(exercise(tmp_path, silent_read=True))
    assert isinstance(result, cb.BridgeError)
    assert str(result) == 'codex_rpc_timeout:thread/read'
    assert not result.ambiguous
    assert not any(r['method'].startswith('turn/') for r in calls)
