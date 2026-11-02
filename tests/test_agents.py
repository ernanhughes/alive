import asyncio
import sys

import pytest

from alive.agents import PiRunner, pi_status
from alive.providers import MetaProvider, MockProvider


async def test_pi_rpc_stream_and_result(settings, tmp_path):
    rpc = tmp_path / "rpc.py"
    rpc.write_text("""import json,sys,time
assert '--no-tools' in sys.argv and '--no-mcp' in sys.argv
request=json.loads(sys.stdin.readline())
assert request['type']=='prompt'
events=[{'type':'response','id':request['id'],'success':True},
 {'type':'message_update','assistantMessageEvent':{'type':'text_delta','delta':'Examining'}},
 {'type':'message_end','message':{'role':'assistant',
   'content':[{'type':'text','text':'Verified fixture'}],'usage':{'input':5}}},
 {'type':'agent_end'}]
for e in events: print(json.dumps(e),flush=True)
time.sleep(60)
""")
    settings.alive_pi_command = [sys.executable, str(rpc)]
    settings.alive_workspace.mkdir()
    progress = []

    async def update(event):
        progress.append(event)

    result, usage = await PiRunner(settings).run("controlled task", update)
    assert result == "Verified fixture" and usage["input"] == 5
    assert progress[0]["text"] == "Examining"


async def test_pi_error_timeout_and_cancellation(settings, tmp_path):
    rpc = tmp_path / "rpc.py"
    settings.alive_pi_command = [sys.executable, str(rpc)]
    settings.alive_workspace.mkdir()
    rpc.write_text(
        'import sys; print(\'{"type":"response","success":false}\',flush=True); sys.stdin.read()'
    )
    with pytest.raises(RuntimeError, match="rejected"):
        await PiRunner(settings).run("task", lambda e: asyncio.sleep(0))
    rpc.write_text("import time;time.sleep(60)")
    settings.alive_agent_timeout = 1
    with pytest.raises(TimeoutError):
        await PiRunner(settings).run("task", lambda e: asyncio.sleep(0))
    task = asyncio.create_task(PiRunner(settings).run("task", lambda e: asyncio.sleep(0)))
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_pi_status_uses_the_pinned_runtime_and_a_detected_ollama_model(settings, monkeypatch):
    monkeypatch.setattr("alive.agents.pi_command", lambda _: (["node", "cli.js"], "pinned"))
    status = pi_status(
        settings,
        {
            "available": True,
            "models": ["qwen2.5:0.5b"],
            "chat_model": "qwen2.5:0.5b",
            "embedding_model": "all-minilm:l6-v2",
            "reason": "ok",
        },
    )
    assert status["installed"] is True
    assert status["configured"] is True
    assert status["provider"] == "ollama"
    assert status["model"] == "qwen2.5:0.5b"
    assert status["auto_detected"] is True
    assert status["pinned"] is True


async def test_provider_contract(settings):
    mock = MockProvider()
    assert (await mock.generate("test")).text == (await mock.generate("test")).text
    assert (await mock.decide("test"))["action"] == "propose_goal"
    assert [chunk async for chunk in mock.stream("test")]
    assert not MetaProvider(settings).capabilities()["configured"]
    with pytest.raises(RuntimeError, match="not configured"):
        await MetaProvider(settings).generate("test")
