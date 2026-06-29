import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkbenchShell, type RuntimeArtifact } from "./workbench-shell";

describe("assistant-ui-first workbench shell", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the enterprise workbench around an assistant-ui thread slot", () => {
    render(<WorkbenchShell thread={<div data-testid="assistant-thread-slot">Thread</div>} />);

    expect(screen.getByRole("navigation", { name: "工作台导航" })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "Agent 对话" })).toBeInTheDocument();
    expect(screen.getByTestId("assistant-thread-slot")).toBeInTheDocument();
    expect(screen.queryByText("默认工作空间")).not.toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "运行证据面板" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "展开运行证据" }));
    expect(screen.getByText("运行证据")).toBeInTheDocument();
    expect(screen.getByText("业务插件待接入")).toBeInTheDocument();
    expect(document.querySelector('[data-slot="sidebar"]')).toBeInTheDocument();
    expect(document.querySelectorAll('[data-slot="card"]').length).toBeGreaterThanOrEqual(3);
    expect(document.querySelector('[data-slot="tabs"]')).toBeInTheDocument();
    expect(document.querySelector('[data-slot="scroll-area"]')).toBeInTheDocument();
  });

  it("loads recent threads into the left sidebar", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("/api/threads?")) {
        return Response.json({
          threads: [
            {
              thread_id: "thread_recent_plan",
              title: "帮我制定一阶段验收计划",
              workspace_id: "workspace_default",
              last_message: "已生成一阶段验收计划。",
              message_count: 2,
            },
            {
              thread_id: "thread_recent_file",
              title: "读取 mvp-stage-plan.md 文件",
              workspace_id: "workspace_default",
              last_message: "已读取工作空间文件：mvp-stage-plan.md。",
              message_count: 2,
            },
          ],
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<WorkbenchShell thread={<div data-testid="assistant-thread-slot">Thread</div>} />);

    await waitFor(() => {
      expect(screen.getByText("最近会话")).toBeInTheDocument();
      expect(screen.getByText("帮我制定一阶段验收计划")).toBeInTheDocument();
      expect(screen.getByText("读取 mvp-stage-plan.md 文件")).toBeInTheDocument();
    });
    expect(screen.getAllByText("2 条消息").length).toBe(2);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/threads?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo",
    );
  });

  it("renders the latest runtime artifact in the inspector", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/diagnostics") {
        return Response.json({ status: "ok", phase: "phase_one", checks: { sqlite: "ok" } });
      }
      if (url === "/api/runs/run_test/events") {
        return Response.json({ events: [] });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    const artifact: RuntimeArtifact = {
      title: "一阶段验收计划",
      summary: "已生成 4 个验收步骤",
      auditEventId: "audit_event_id_evt_test",
      events: ["run.created", "intent.classified", "tool.completed", "artifact.created"],
      toolName: "plan.update",
      artifactId: "art_test",
      runId: "run_test",
    };

    render(
      <WorkbenchShell
        thread={<div />}
        runtimeArtifact={artifact}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "展开运行证据" }));
    expect(screen.getByText("一阶段验收计划")).toBeInTheDocument();
    expect(screen.getByText("已生成 4 个验收步骤")).toBeInTheDocument();
    expect(screen.getByText("plan.update")).toBeInTheDocument();
    expect(screen.getByText("art_test")).toBeInTheDocument();
    expect(screen.getByText("run_test")).toBeInTheDocument();
    expect(screen.getByText("audit_event_id_evt_test")).toBeInTheDocument();
  });

  it("renders an in-progress runtime artifact before final tool output exists", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/diagnostics") {
        return Response.json({ status: "ok", phase: "phase_one", checks: { sqlite: "ok" } });
      }
      if (url === "/api/runs/run_live/events") {
        return Response.json({ events: [] });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(
      <WorkbenchShell
        thread={<div />}
        runtimeArtifact={{
          title: "Agent 正在运行",
          summary: "调用模型",
          events: ["model.started"],
          toolName: "通用 Agent",
          runId: "run_live",
          status: "running",
          latestEvent: "model.started",
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "展开运行证据" }));
    expect(screen.getByText("Agent 正在运行")).toBeInTheDocument();
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("调用模型")).toBeInTheDocument();
    expect(screen.getByText("run_live")).toBeInTheDocument();
    expect(screen.getByText("model.started")).toBeInTheDocument();
    expect(screen.getByText("等待运行后生成 audit_event_id")).toBeInTheDocument();
  });


  it("syncs runtime events from the run events API when a run id is available", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/diagnostics") {
        return Response.json({ status: "ok", phase: "phase_one", checks: { sqlite: "ok" } });
      }
      if (url === "/api/runs/run_event_sync") {
        return Response.json({
          run_id: "run_event_sync",
          status: "completed",
          question: "运行诊断",
          steps: [
            {
              step_id: "step_1",
              step_type: "intent",
              status: "completed",
              payload: { intent: "diagnostic_check" },
            },
            {
              step_id: "step_2",
              step_type: "tool:diagnostic.check",
              status: "running",
              payload: { tool_id: "diagnostic.check" },
            },
            {
              step_id: "step_3",
              step_type: "artifact:diagnostic_report",
              status: "completed",
              payload: { artifact_type: "diagnostic_report" },
            },
          ],
        });
      }
      if (url === "/api/runs/run_event_sync/events") {
        return Response.json({
          events: [
            {
              event_id: "evt_1",
              event_type: "run.created",
              payload_digest: "digest_1",
              occurred_at: "2026-06-26T00:00:00+00:00",
            },
            {
              event_id: "evt_2",
              event_type: "tool.completed",
              payload_digest: "digest_2",
              occurred_at: "2026-06-26T00:00:01+00:00",
            },
          ],
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(
      <WorkbenchShell
        thread={<div />}
        runtimeArtifact={{
          title: "诊断工具",
          summary: "已生成诊断报告",
          auditEventId: "evt_audit",
          events: ["fallback.event"],
          toolName: "diagnostic.check",
          runId: "run_event_sync",
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "展开运行证据" }));
    fireEvent.click(screen.getByRole("tab", { name: "事件" }));

    await waitFor(() => {
      expect(screen.getByText("执行步骤")).toBeInTheDocument();
      expect(screen.getAllByText("已同步 3 个执行步骤").length).toBeGreaterThan(0);
      expect(screen.getByText("tool:diagnostic.check")).toBeInTheDocument();
      expect(screen.getByText("running")).toBeInTheDocument();
      expect(screen.getByText("已同步 2 条运行事件")).toBeInTheDocument();
      expect(screen.getByText("run.created")).toBeInTheDocument();
      expect(screen.getByText("tool.completed")).toBeInTheDocument();
    });
    expect(screen.queryByText("fallback.event")).not.toBeInTheDocument();
  });

  it("refreshes run evidence when the same run reaches a terminal event", async () => {
    let eventsFetchCount = 0;
    let runFetchCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/diagnostics") {
        return Response.json({ status: "ok", phase: "phase_one", checks: { sqlite: "ok" } });
      }
      if (url === "/api/runs/run_refresh") {
        runFetchCount += 1;
        return Response.json({
          run_id: "run_refresh",
          status: runFetchCount > 1 ? "failed" : "running",
          question: "触发失败工具测试",
          steps: [
            {
              step_id: "step_tool",
              step_type: "tool:diagnostic.check",
              status: runFetchCount > 1 ? "failed" : "running",
              payload: { tool_id: "diagnostic.check" },
            },
          ],
        });
      }
      if (url === "/api/runs/run_refresh/events") {
        eventsFetchCount += 1;
        return Response.json({
          events: eventsFetchCount > 1
            ? [
                { event_id: "evt_1", event_type: "run.created", payload_digest: "digest_1" },
                { event_id: "evt_2", event_type: "tool.failed", payload_digest: "digest_2" },
                { event_id: "evt_3", event_type: "run.failed", payload_digest: "digest_3" },
              ]
            : [
                { event_id: "evt_1", event_type: "run.created", payload_digest: "digest_1" },
                { event_id: "evt_2", event_type: "tool.started", payload_digest: "digest_2" },
              ],
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    const runningArtifact: RuntimeArtifact = {
      title: "诊断工具",
      summary: "正在执行工具",
      events: ["run.created", "tool.started"],
      toolName: "diagnostic.check",
      runId: "run_refresh",
      status: "running",
      latestEvent: "tool.started",
    };
    const failedArtifact: RuntimeArtifact = {
      ...runningArtifact,
      summary: "工具执行失败",
      events: ["run.created", "tool.failed", "run.failed"],
      status: "failed",
      latestEvent: "run.failed",
    };

    const { rerender } = render(<WorkbenchShell thread={<div />} runtimeArtifact={runningArtifact} />);
    fireEvent.click(screen.getByRole("button", { name: "展开运行证据" }));
    fireEvent.click(screen.getByRole("tab", { name: "事件" }));

    await waitFor(() => {
      expect(screen.getByText("tool.started")).toBeInTheDocument();
    });

    rerender(<WorkbenchShell thread={<div />} runtimeArtifact={failedArtifact} />);

    await waitFor(() => {
      expect(eventsFetchCount).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("run.failed")).toBeInTheDocument();
      expect(screen.getByText("tool.failed")).toBeInTheDocument();
      expect(screen.getAllByText("failed").length).toBeGreaterThan(0);
    });
  });

  it("loads a selected recent thread into the central conversation area", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("/api/threads?")) {
        return Response.json({
          threads: [
            {
              thread_id: "thread_history",
              title: "历史会话标题",
              workspace_id: "workspace_default",
              last_message: "历史助手回复",
              message_count: 2,
            },
          ],
        });
      }
      if (url === "/api/diagnostics") {
        return Response.json({ status: "ok", phase: "phase_one", checks: { sqlite: "ok" } });
      }
      if (url === "/api/threads/thread_history?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo") {
        return Response.json({
          thread: {
            thread_id: "thread_history",
            title: "历史会话标题",
            workspace_id: "workspace_default",
          },
          messages: [
            {
              message_id: "msg_user",
              role: "user",
              content: "历史用户问题",
              run_id: null,
            },
            {
              message_id: "msg_assistant",
              role: "assistant",
              content: "历史助手回复",
              run_id: "run_history",
            },
          ],
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    const handleNewThread = vi.fn();
    render(<WorkbenchShell thread={<div data-testid="assistant-thread-slot">Thread</div>} onNewThread={handleNewThread} />);

    const main = screen.getByRole("main", { name: "Agent 对话" });
    await waitFor(() => {
      expect(screen.getByText("历史会话标题")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /历史会话标题/ }));

    await waitFor(() => {
      expect(within(main).getByText("历史用户问题")).toBeInTheDocument();
      expect(within(main).getByText("历史助手回复")).toBeInTheDocument();
    });
    expect(within(main).queryByText("run_history")).not.toBeInTheDocument();
    expect(within(main).getByTestId("assistant-thread-slot")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "新建任务" }));
    expect(within(main).getByTestId("assistant-thread-slot")).toBeInTheDocument();
    expect(handleNewThread).toHaveBeenCalledTimes(1);
  });

  it("loads diagnostics from the phase-one diagnostics API", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("/api/threads?")) {
        return Response.json({ threads: [] });
      }
      if (url === "/api/diagnostics") {
        return Response.json({
          status: "ok",
          phase: "phase_one",
          checks: {
            sqlite: "ok",
            model: "configured",
            business_plugins: "disabled_until_phase_two",
          },
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<WorkbenchShell thread={<div />} />);
    fireEvent.click(screen.getByRole("button", { name: "展开运行证据" }));
    fireEvent.click(screen.getByRole("tab", { name: "诊断" }));

    await waitFor(() => {
      expect(screen.getByText("sqlite: ok")).toBeInTheDocument();
      expect(screen.getByText("model: configured")).toBeInTheDocument();
      expect(screen.getByText("business_plugins: disabled_until_phase_two")).toBeInTheDocument();
    });
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/diagnostics");
  });

  it("opens settings and loads configured models", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/diagnostics") {
        return Response.json({
          status: "ok",
          phase: "phase_one",
          checks: { sqlite: "ok", model: "configured" },
        });
      }
      if (url === "/api/models") {
        return Response.json({
          models: [
            {
              model_id: "qwen3.7-plus",
              provider: "openai-compatible",
              base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
              configured: true,
              capabilities: ["chat", "streaming", "tool_calling"],
            },
          ],
        });
      }
      if (url === "/api/models/test") {
        return Response.json({ model_id: "qwen3.7-plus", status: "configured" });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<WorkbenchShell thread={<div />} />);
    fireEvent.click(screen.getByRole("button", { name: "设置与模型" }));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText("模型与设置")).toBeInTheDocument();
      expect(screen.getByText("qwen3.7-plus")).toBeInTheDocument();
      expect(screen.getByText("openai-compatible")).toBeInTheDocument();
      expect(screen.getByText("模型已配置")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "测试连接" }));
    await waitFor(() => {
      expect(screen.getByText("连接状态：configured")).toBeInTheDocument();
    });
  });

  it("exposes cancel and retry actions for the current run", async () => {
    const artifact: RuntimeArtifact = {
      title: "诊断工具",
      summary: "工具执行失败",
      auditEventId: "evt_failed",
      events: ["run.created", "tool.failed", "run.failed"],
      toolName: "diagnostic.check",
      runId: "run_failed",
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/diagnostics") {
        return Response.json({
          status: "ok",
          phase: "phase_one",
          checks: { sqlite: "ok" },
        });
      }
      if (url === "/api/runs/run_failed/cancel" && init?.method === "POST") {
        return Response.json({ run_id: "run_failed", status: "cancelled", events: ["run.cancelled"] });
      }
      if (url === "/api/runs/run_failed/retry" && init?.method === "POST") {
        return Response.json({
          run_id: "run_retry",
          retry_of_run_id: "run_failed",
          status: "created",
          events: ["run.created", "retry_of_run"],
        });
      }
      if (url === "/api/runs/run_failed/events") {
        return Response.json({ events: [] });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<WorkbenchShell thread={<div />} runtimeArtifact={artifact} />);

    fireEvent.click(screen.getByRole("button", { name: "展开运行证据" }));
    fireEvent.click(screen.getByRole("button", { name: "取消运行" }));
    await waitFor(() => {
      expect(screen.getByText("运行已取消：run_failed")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "重试运行" }));
    await waitFor(() => {
      expect(screen.getByText("已创建重试运行：run_retry")).toBeInTheDocument();
    });
  });
});
