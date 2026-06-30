import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-plus"


def load_local_env() -> None:
    if os.getenv("WORKBENCH_DISABLE_LOCAL_ENV") == "1":
        return
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if not item or item.startswith("#") or "=" not in item:
            continue
        key, value = item.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def model_configured() -> bool:
    return bool(os.getenv("BAILIAN_API_KEY") or os.getenv("OPENAI_COMPATIBLE_API_KEY"))


def chat_completion(text: str) -> dict[str, str]:
    load_local_env()
    api_key = os.getenv("BAILIAN_API_KEY") or os.getenv("OPENAI_COMPATIBLE_API_KEY")
    if not api_key:
        return {
            "message": "未配置模型服务。请在服务端环境变量中配置 BAILIAN_API_KEY 或 OPENAI_COMPATIBLE_API_KEY。",
            "provider": "not_configured",
            "model": os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL),
        }

    base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是公司工作台 Agent。回答要简洁、可执行；如需业务系统数据，应说明需要选择插件。",
            },
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return {
            "message": f"模型服务调用失败：{error.__class__.__name__}",
            "provider": "aliyun-bailian",
            "model": model,
        }

    choice = _first_choice(body)
    content = choice.get("message", {}).get("content", "")
    return {
        "message": content or "模型服务未返回内容。",
        "provider": "aliyun-bailian",
        "model": model,
    }


def chat_completion_with_tools(text: str, tools: list[dict]) -> dict:
    load_local_env()
    api_key = os.getenv("BAILIAN_API_KEY") or os.getenv("OPENAI_COMPATIBLE_API_KEY")
    if not api_key:
        return {
            "message": "未配置模型服务。请在服务端环境变量中配置 BAILIAN_API_KEY 或 OPENAI_COMPATIBLE_API_KEY。",
            "provider": "not_configured",
            "model": os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL),
        }

    base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是公司工作台 Agent。回答要简洁、可执行。"
                    "当用户请求需要读取设置、诊断、本地分析、工作空间文件或记忆时，优先调用可用工具。"
                    "不得编造工具未返回的数据。"
                ),
            },
            {"role": "user", "content": text},
        ],
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return {
            "message": f"模型服务调用失败：{error.__class__.__name__}",
            "provider": "aliyun-bailian",
            "model": model,
        }

    message = _first_choice(body).get("message", {})
    tool_calls = []
    for raw_call in message.get("tool_calls") or []:
        function = raw_call.get("function") or {}
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        except json.JSONDecodeError:
            arguments = {}
        tool_calls.append(
            {
                "id": raw_call.get("id"),
                "name": function.get("name"),
                "arguments": arguments if isinstance(arguments, dict) else {},
            }
        )
    return {
        "message": message.get("content") or "",
        "provider": "aliyun-bailian",
        "model": model,
        "tool_calls": tool_calls,
    }


def chat_completion_messages(messages: list[dict], tools: list[dict] | None = None) -> dict:
    load_local_env()
    api_key = os.getenv("BAILIAN_API_KEY") or os.getenv("OPENAI_COMPATIBLE_API_KEY")
    if not api_key:
        return {
            "message": "未配置模型服务。请在服务端环境变量中配置 BAILIAN_API_KEY 或 OPENAI_COMPATIBLE_API_KEY。",
            "provider": "not_configured",
            "model": os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL),
        }

    base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return {
            "message": f"模型服务调用失败：{error.__class__.__name__}",
            "provider": "aliyun-bailian",
            "model": model,
        }

    message = _first_choice(body).get("message", {})
    return {
        "message": message.get("content") or "",
        "provider": "aliyun-bailian",
        "model": model,
    }


def chat_completion_stream(text: str, on_delta: Callable[[str], None]) -> dict:
    return _chat_completion_stream(text, on_delta)


def chat_completion_stream_with_tools(text: str, tools: list[dict], on_delta: Callable[[str], None]) -> dict:
    return _chat_completion_stream(text, on_delta, tools=tools)


def _chat_completion_stream(text: str, on_delta: Callable[[str], None], tools: list[dict] | None = None) -> dict:
    load_local_env()
    api_key = os.getenv("BAILIAN_API_KEY") or os.getenv("OPENAI_COMPATIBLE_API_KEY")
    model = os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL)
    if not api_key:
        message = "未配置模型服务。请在服务端环境变量中配置 BAILIAN_API_KEY 或 OPENAI_COMPATIBLE_API_KEY。"
        on_delta(message)
        return {
            "message": message,
            "provider": "not_configured",
            "model": model,
        }

    base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是公司工作台 Agent。回答要简洁、可执行；如需业务系统数据，应说明需要选择插件。",
            },
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    chunks: list[str] = []
    tool_call_parts: dict[int, dict[str, str]] = {}
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    body = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choice = _first_choice(body)
                if not choice:
                    continue
                delta = choice.get("delta", {}).get("content", "")
                if delta:
                    chunks.append(delta)
                    on_delta(delta)
                for raw_tool_call in choice.get("delta", {}).get("tool_calls") or []:
                    if not isinstance(raw_tool_call, dict):
                        continue
                    index = int(raw_tool_call.get("index") or 0)
                    part = tool_call_parts.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    if raw_tool_call.get("id"):
                        part["id"] += str(raw_tool_call["id"])
                    function = raw_tool_call.get("function") or {}
                    if function.get("name"):
                        part["name"] += str(function["name"])
                    if function.get("arguments"):
                        part["arguments"] += str(function["arguments"])
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        message = f"模型服务调用失败：{error.__class__.__name__}"
        on_delta(message)
        return {
            "message": message,
            "provider": "aliyun-bailian",
            "model": model,
        }

    content = "".join(chunks)
    tool_calls = _assemble_stream_tool_calls(tool_call_parts)
    if not content and not tool_calls:
        content = "模型服务未返回内容。"
        on_delta(content)
    return {
        "message": content,
        "provider": "aliyun-bailian",
        "model": model,
        "tool_calls": tool_calls,
    }


def _first_choice(body: dict) -> dict:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    first = choices[0]
    return first if isinstance(first, dict) else {}


def _assemble_stream_tool_calls(tool_call_parts: dict[int, dict[str, str]]) -> list[dict]:
    tool_calls = []
    for index in sorted(tool_call_parts):
        part = tool_call_parts[index]
        name = part.get("name") or ""
        if not name:
            continue
        raw_arguments = part.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            arguments = {}
        tool_calls.append(
            {
                "id": part.get("id") or f"toolcall_{index + 1}",
                "name": name,
                "arguments": arguments if isinstance(arguments, dict) else {},
            }
        )
    return tool_calls
