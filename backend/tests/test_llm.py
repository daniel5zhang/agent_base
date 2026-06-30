import json

from app.llm import chat_completion_messages, chat_completion_stream


class FakeSSEHTTPResponse:
    def __init__(self, events: list[dict]):
        self._lines = [
            f"data: {json.dumps(event, ensure_ascii=False)}\n".encode("utf-8")
            for event in events
        ]
        self._lines.append(b"data: [DONE]\n")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._lines)


class FakeJSONHTTPResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_chat_completion_stream_collects_openai_compatible_tool_call_deltas(monkeypatch):
    events = [
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "diagnostic__check",
                                    "arguments": "{\"scope\"",
                                },
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {
                                    "arguments": ":\"runtime\"}",
                                },
                            }
                        ]
                    }
                }
            ]
        },
    ]

    monkeypatch.setenv("WORKBENCH_DISABLE_LOCAL_ENV", "1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "qwen-test")
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeSSEHTTPResponse(events))

    deltas: list[str] = []
    result = chat_completion_stream("检查运行状态", deltas.append)

    assert deltas == []
    assert result["message"] == ""
    assert result["provider"] == "aliyun-bailian"
    assert result["model"] == "qwen-test"
    assert result["tool_calls"] == [
        {
            "id": "call_1",
            "name": "diagnostic__check",
            "arguments": {"scope": "runtime"},
        }
    ]


def test_chat_completion_stream_ignores_empty_choice_chunks(monkeypatch):
    events = [
        {"choices": []},
        {"choices": [{"delta": {"content": "企业"}}]},
        {"choices": []},
        {"choices": [{"delta": {"content": "工作台"}}]},
    ]

    monkeypatch.setenv("WORKBENCH_DISABLE_LOCAL_ENV", "1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "qwen-test")
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeSSEHTTPResponse(events))

    deltas: list[str] = []
    result = chat_completion_stream("介绍自己", deltas.append)

    assert deltas == ["企业", "工作台"]
    assert result["message"] == "企业工作台"
    assert result["tool_calls"] == []


def test_chat_completion_messages_sends_openai_compatible_tool_role_payload(monkeypatch):
    captured = {}
    messages = [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "检查运行状态"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "diagnostic__check", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "diagnostic__check",
            "content": "{\"status\":\"ok\"}",
        },
    ]

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeJSONHTTPResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "最终回复",
                        }
                    }
                ]
            }
        )

    monkeypatch.setenv("WORKBENCH_DISABLE_LOCAL_ENV", "1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "qwen-test")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = chat_completion_messages(messages)

    assert result == {"message": "最终回复", "provider": "aliyun-bailian", "model": "qwen-test"}
    assert captured["payload"]["model"] == "qwen-test"
    assert captured["payload"]["messages"] == messages
    assert "tools" not in captured["payload"]
