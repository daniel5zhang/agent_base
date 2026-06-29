import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

type MockRun = {
  run_id: string;
  thread_id: string;
  workspace_id: string;
  status: "completed" | "blocked" | "failed" | "cancelled";
  intent: string;
  response: string;
  tool_invocations: string[];
  artifacts: Array<{ artifact_id: string; title: string; artifact_type: string }>;
  memory_ids: string[];
  audit_event_id: string;
  events: string[];
};

function sse(event: string, data: unknown) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function runtimeEvent(event_type: string, run_id = "run_test", payload?: Record<string, unknown>) {
  return {
    event_id: `evt_${event_type.replaceAll(".", "_")}`,
    event_type,
    run_id,
    thread_id: "thread_default",
    workspace_id: "workspace_default",
    payload_digest: `digest_${event_type}`,
    occurred_at: "2026-06-26T00:00:00+00:00",
    payload,
  };
}

function modelDelta(delta: string, run_id = "run_model") {
  return {
    ...runtimeEvent("model.delta", run_id),
    payload: { delta },
  };
}

function streamResponse(run: MockRun) {
  return new Response([
    ...run.events.map((event) => sse("runtime_event", runtimeEvent(event, run.run_id))),
    sse("final_result", run),
    sse("stream_end", { status: "closed" }),
  ].join(""), {
    headers: { "Content-Type": "text/event-stream" },
  });
}

function extractToolCallIds(body: string) {
  return [...body.matchAll(/"toolCallId":"([^"]+)"/g)].map((match) => match[1]);
}

function hangingStreamResponse(runId: string) {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(sse("runtime_event", runtimeEvent("run.created", runId))));
      controller.enqueue(encoder.encode(sse("runtime_event", runtimeEvent("model.started", runId))));
    },
  }), {
    headers: { "Content-Type": "text/event-stream" },
  });
}

async function postChat(text: string) {
  return POST(new Request("http://localhost/api/chat", {
    method: "POST",
    body: JSON.stringify({
      messages: [
        {
          id: "msg_1",
          role: "user",
          parts: [{ type: "text", text }],
        },
      ],
    }),
  }));
}

describe("assistant-ui chat route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("streams live runtime events before the final tool result", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const run: MockRun = {
      status: "completed",
      intent: "plan",
      response: "已生成一阶段验收计划。审计编号：evt_tool_completed",
      run_id: "run_test",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      tool_invocations: ["intent.classify", "plan.update", "artifact.create"],
      artifacts: [{ artifact_id: "art_test", title: "一阶段验收计划", artifact_type: "plan" }],
      memory_ids: [],
      audit_event_id: "evt_tool_completed",
      events: [
        "run.created",
        "message.received",
        "intent.classified",
        "context.built",
        "tool.planned",
        "tool.started",
        "tool.completed",
        "artifact.created",
        "run.completed",
      ],
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("http://python-server.test/api/agent/run/stream");
      expect(init?.method).toBe("POST");
      expect(init?.headers).toEqual({ "Content-Type": "application/json", Accept: "text/event-stream" });
      expect(JSON.parse(String(init?.body))).toMatchObject({
        thread_id: "thread_msg_1",
      });
      return streamResponse(run);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await postChat("帮我制定一阶段验收计划");

    expect(response.headers.get("content-type")).toContain("text/event-stream");
    const body = await response.text();
    expect(body).toContain("连接 Agent 运行时");
    expect(body).toContain("data-runtime");
    expect(body).toContain("run_test");
    expect(body).toContain("plan.update");
    expect(body).toContain("artifact.created");
    expect(body).toContain("evt_tool_completed");
    expect(body).toContain("art_test");
    expect(body.indexOf("连接 Agent 运行时")).toBeLessThan(body.indexOf("run.created"));
    expect(body.indexOf("tool.started")).toBeLessThan(body.indexOf("tool.completed"));
    expect(body.indexOf("tool.completed")).toBeLessThan(body.indexOf("evt_tool_completed"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not pretend business plugin requests succeeded in phase one", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const run: MockRun = {
      run_id: "run_business",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      status: "blocked",
      intent: "business_plugin_required",
      response: "该请求需要业务插件能力，业务插件将在二阶段启用。一阶段不会返回模拟业务数据。",
      tool_invocations: ["intent.classify", "plugin.catalog"],
      artifacts: [],
      memory_ids: [],
      audit_event_id: "evt_business",
      events: ["run.created", "intent.classified", "tool.completed", "run.completed"],
    };
    vi.stubGlobal("fetch", vi.fn(async () => streamResponse(run)));

    const response = await postChat("查 2026 年所有惠民保项目总保费");

    const body = await response.text();
    expect(body).toContain("intent.classified");
    expect(body).toContain("business_plugin_required");
    expect(body).toContain("业务插件将在二阶段启用");
    expect(body).not.toContain("12.36 亿元");
    expect(body).not.toContain("ask_data.query");
  });

  it("includes tool names in streaming runtime data for live execution steps", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const run: MockRun = {
      status: "completed",
      intent: "diagnostic",
      response: "诊断完成。",
      run_id: "run_tool_live",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      tool_invocations: ["intent.classify", "diagnostic.check"],
      artifacts: [],
      memory_ids: [],
      audit_event_id: "evt_tool_live",
      events: ["run.created", "tool.started", "tool.completed", "run.completed"],
    };
    vi.stubGlobal("fetch", vi.fn(async () => new Response([
      sse("runtime_event", runtimeEvent("run.created", run.run_id)),
      sse("runtime_event", runtimeEvent("tool.started", run.run_id, { tool_id: "diagnostic.check" })),
      sse("final_result", run),
      sse("stream_end", { status: "closed" }),
    ].join(""), {
      headers: { "Content-Type": "text/event-stream" },
    })));

    const response = await postChat("运行诊断");

    const body = await response.text();
    expect(body).toContain("data-runtime");
    expect(body).toContain('"toolName":"diagnostic.check"');
    expect(body.indexOf('"toolName":"diagnostic.check"')).toBeLessThan(body.indexOf("evt_tool_live"));
  });

  it("uses run-scoped tool call ids so repeated tools do not collide in assistant-ui", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const firstRun: MockRun = {
      status: "completed",
      intent: "diagnostic",
      response: "第一次诊断完成。",
      run_id: "run_diagnostic_first",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      tool_invocations: ["intent.classify", "diagnostic.check"],
      artifacts: [],
      memory_ids: [],
      audit_event_id: "evt_first",
      events: ["run.created", "tool.completed", "run.completed"],
    };
    const secondRun: MockRun = {
      ...firstRun,
      response: "第二次诊断完成。",
      run_id: "run_diagnostic_second",
      audit_event_id: "evt_second",
    };
    const runs = [firstRun, secondRun];
    vi.stubGlobal("fetch", vi.fn(async () => streamResponse(runs.shift() ?? secondRun)));

    const firstBody = await (await postChat("运行诊断")).text();
    const secondBody = await (await postChat("再次运行诊断")).text();

    const firstIds = extractToolCallIds(firstBody);
    const secondIds = extractToolCallIds(secondBody);
    expect(firstIds).toEqual(["tool_diagnostic_check_run_diagnostic_first", "tool_diagnostic_check_run_diagnostic_first"]);
    expect(secondIds).toEqual(["tool_diagnostic_check_run_diagnostic_second", "tool_diagnostic_check_run_diagnostic_second"]);
    expect(new Set([...firstIds, ...secondIds]).size).toBe(2);
  });

  it("streams model deltas as assistant text before final_result for general chat", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const run: MockRun = {
      run_id: "run_model",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      status: "completed",
      intent: "general_chat",
      response: "这是模型回答",
      tool_invocations: ["intent.classify"],
      artifacts: [],
      memory_ids: [],
      audit_event_id: "evt_model",
      events: [
        "run.created",
        "message.received",
        "intent.classified",
        "context.built",
        "model.selected",
        "model.started",
        "model.delta",
        "model.delta",
        "model.completed",
        "run.completed",
      ],
    };
    vi.stubGlobal("fetch", vi.fn(async () => new Response([
      sse("runtime_event", runtimeEvent("run.created", run.run_id)),
      sse("runtime_event", runtimeEvent("model.started", run.run_id)),
      sse("model_delta", modelDelta("这是", run.run_id)),
      sse("model_delta", modelDelta("模型回答", run.run_id)),
      sse("runtime_event", runtimeEvent("model.completed", run.run_id)),
      sse("final_result", run),
      sse("stream_end", { status: "closed" }),
    ].join(""), {
      headers: { "Content-Type": "text/event-stream" },
    })));

    const response = await postChat("用一句话介绍工作台");

    const body = await response.text();
    expect(body).toContain("answer_streaming_model");
    expect(body).toContain("data-runtime");
    expect(body).toContain("这是");
    expect(body).toContain("模型回答");
    expect(body.indexOf("model.started")).toBeLessThan(body.indexOf("这是"));
    expect(body.indexOf("这是")).toBeLessThan(body.indexOf("模型回答"));
    expect(body.indexOf("模型回答")).toBeLessThan(body.indexOf("model.completed"));
    expect(body).not.toContain("answer_general_chat");
  });

  it("keeps streamed assistant text and records cancelled final status", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const run: MockRun = {
      run_id: "run_cancelled",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      status: "cancelled",
      intent: "general_chat",
      response: "运行已取消。",
      tool_invocations: ["intent.classify"],
      artifacts: [],
      memory_ids: [],
      audit_event_id: "evt_cancelled",
      events: ["run.created", "model.started", "model.delta", "run.cancelled"],
    };
    vi.stubGlobal("fetch", vi.fn(async () => new Response([
      sse("runtime_event", runtimeEvent("run.created", run.run_id)),
      sse("runtime_event", runtimeEvent("model.started", run.run_id)),
      sse("model_delta", modelDelta("第一段", run.run_id)),
      sse("runtime_event", runtimeEvent("run.cancelled", run.run_id)),
      sse("final_result", run),
      sse("stream_end", { status: "closed" }),
    ].join(""), {
      headers: { "Content-Type": "text/event-stream" },
    })));

    const response = await postChat("请持续输出一段通用说明");

    const body = await response.text();
    expect(body).toContain("第一段");
    expect(body).toContain("run.cancelled");
    expect(body).toContain('"status":"cancelled"');
    expect(body).not.toContain("answer_general_chat");
  });

  it("cancels the Python run when the assistant-ui request is aborted", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "http://python-server.test/api/agent/run/stream") {
        return hangingStreamResponse("run_abort");
      }
      if (url === "http://python-server.test/api/runs/run_abort/cancel" && init?.method === "POST") {
        expect(init.body).toBe(JSON.stringify({ user_id: "user_demo", reason: "用户停止生成" }));
        return Response.json({ run_id: "run_abort", status: "cancelled", events: ["run.cancelled"] });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const abortController = new AbortController();
    const response = await POST(new Request("http://localhost/api/chat", {
      method: "POST",
      signal: abortController.signal,
      body: JSON.stringify({
        messages: [
          {
            id: "msg_1",
            role: "user",
            parts: [{ type: "text", text: "请持续输出一段通用说明" }],
          },
        ],
      }),
    }));

    const readPromise = response.text();
    await new Promise((resolve) => setTimeout(resolve, 20));
    abortController.abort();
    await readPromise;

    expect(fetchMock).toHaveBeenCalledWith(
      "http://python-server.test/api/runs/run_abort/cancel",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("streams diagnostic tool output from the server runtime", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    vi.stubGlobal("fetch", vi.fn(async () => streamResponse({
      status: "completed",
      intent: "diagnostic_check",
      response: "诊断完成：服务端、SQLite、模型配置和一阶段工具状态已记录。",
      run_id: "run_diagnostic",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      tool_invocations: ["intent.classify", "diagnostic.check", "artifact.create"],
      artifacts: [{ artifact_id: "art_diagnostic", title: "诊断报告", artifact_type: "diagnostic_report" }],
      memory_ids: [],
      audit_event_id: "evt_diagnostic",
      events: ["run.created", "tool.started", "tool.completed", "artifact.created", "run.completed"],
    })));

    const response = await postChat("运行诊断检查服务端模型和工具状态");

    const body = await response.text();
    expect(body).toContain("diagnostic.check");
    expect(body).toContain("诊断报告");
    expect(body).toContain("已生成诊断报告");
    expect(body).toContain("evt_diagnostic");
  });

  it("streams local data analysis tool output", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    vi.stubGlobal("fetch", vi.fn(async () => streamResponse({
      status: "completed",
      intent: "local_data_analysis",
      response: "已完成本地数据分析：共 3 个值，合计 60，平均 20。",
      run_id: "run_local_analysis",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      tool_invocations: ["intent.classify", "local_data.analyze", "artifact.create"],
      artifacts: [{ artifact_id: "art_local_analysis", title: "本地数据分析", artifact_type: "local_data_analysis" }],
      memory_ids: [],
      audit_event_id: "evt_local_analysis",
      events: ["run.created", "tool.started", "tool.completed", "artifact.created", "run.completed"],
    })));

    const response = await postChat("本地分析 10 20 30 的平均值");

    const body = await response.text();
    expect(body).toContain("local_data.analyze");
    expect(body).toContain("本地数据分析");
    expect(body).toContain("已生成本地数据分析");
    expect(body).toContain("evt_local_analysis");
  });

  it("streams failed tool state instead of pretending success", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    vi.stubGlobal("fetch", vi.fn(async () => streamResponse({
      status: "failed",
      intent: "tool_failure_test",
      response: "工具执行失败：diagnostic.check 返回 phase_one_failure_test。请重试或查看运行事件。",
      run_id: "run_failed",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      tool_invocations: ["intent.classify", "diagnostic.check"],
      artifacts: [],
      memory_ids: [],
      audit_event_id: "evt_failed",
      events: [
        "run.created",
        "message.received",
        "intent.classified",
        "context.built",
        "tool.planned",
        "tool.started",
        "tool.failed",
        "run.failed",
      ],
    })));

    const response = await postChat("触发失败工具测试");

    const body = await response.text();
    expect(body).toContain('"status":"failed"');
    expect(body).toContain("tool.failed");
    expect(body).toContain("run.failed");
    expect(body).toContain("工具执行失败");
    expect(body).toContain("evt_failed");
  });

  it("streams a visible server-unavailable error when the Python runtime cannot be reached", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    }));

    const response = await postChat("帮我制定一阶段验收计划");

    const body = await response.text();
    expect(body).toContain("answer_error");
    expect(body).toContain("服务端不可用或运行失败");
    expect(body).toContain("ECONNREFUSED");
    expect(body).not.toContain("run.completed");
  });

  it("streams memory read artifact output", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    vi.stubGlobal("fetch", vi.fn(async () => streamResponse({
      status: "completed",
      intent: "memory_read",
      response: "已读取受控记忆，共 1 条。",
      run_id: "run_memory_read",
      thread_id: "thread_default",
      workspace_id: "workspace_default",
      tool_invocations: ["intent.classify", "memory.read", "artifact.create"],
      artifacts: [{ artifact_id: "art_memory", title: "受控记忆快照", artifact_type: "memory_snapshot" }],
      memory_ids: [],
      audit_event_id: "evt_memory",
      events: ["run.created", "tool.completed", "artifact.created", "run.completed"],
    })));

    const response = await postChat("读取我的记忆偏好");

    const body = await response.text();
    expect(body).toContain("memory.read");
    expect(body).toContain("受控记忆快照");
    expect(body).toContain("已读取受控记忆");
    expect(body).toContain("evt_memory");
  });
});
