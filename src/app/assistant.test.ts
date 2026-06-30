import { describe, expect, it } from "vitest";
import {
  extractRuntimeArtifactFromMessages,
  normalizeRuntimeArtifactForThreadState,
} from "./assistant";

describe("assistant runtime artifact extraction", () => {
  it("extracts the latest server tool output regardless of tool name", () => {
    const artifact = extractRuntimeArtifactFromMessages([
      {
        role: "assistant",
        content: [
          {
            type: "tool-call",
            toolName: "plugin.catalog",
            result: {
              title: "插件目录",
              summary: "请求已被一阶段边界阻断",
              audit_event_id: "evt_business",
              events: ["run.created", "tool.completed", "run.completed"],
              run_id: "run_business",
            },
          },
        ],
      },
    ]);

    expect(artifact).toEqual({
      title: "插件目录",
      summary: "请求已被一阶段边界阻断",
      auditEventId: "evt_business",
      events: ["run.created", "tool.completed", "run.completed"],
      toolName: "plugin.catalog",
      artifactId: undefined,
      runId: "run_business",
      status: undefined,
      latestEvent: undefined,
    });
  });

  it("extracts runtime data while a run is still in progress", () => {
    const artifact = extractRuntimeArtifactFromMessages([
      {
        role: "assistant",
        content: [
          {
            type: "data-runtime",
            data: {
              runId: "run_live",
              status: "running",
              title: "Agent 正在运行",
              summary: "当前事件：model.started",
              eventType: "model.started",
              events: ["model.started"],
            },
          },
        ],
      },
    ]);

    expect(artifact).toEqual({
      title: "Agent 正在运行",
      summary: "当前事件：model.started",
      auditEventId: undefined,
      events: ["model.started"],
      toolName: "通用 Agent",
      artifactId: undefined,
      runId: "run_live",
      status: "running",
      latestEvent: "model.started",
      liveSteps: [
        {
          step_id: "live_model_started_0",
          step_type: "model",
          status: "running",
          payload: { event_type: "model.started" },
        },
      ],
    });
  });

  it("projects streaming runtime events into live execution steps", () => {
    const artifact = extractRuntimeArtifactFromMessages([
      {
        role: "assistant",
        content: [
          {
            type: "data-runtime",
            data: {
              runId: "run_live",
              status: "running",
              eventType: "run.created",
              events: ["run.created"],
            },
          },
          {
            type: "data-runtime",
            data: {
              runId: "run_live",
              status: "running",
              eventType: "tool.started",
              toolName: "diagnostic.check",
              events: ["tool.started"],
            },
          },
        ],
      },
    ]);

    expect(artifact).toMatchObject({
      runId: "run_live",
      status: "running",
      latestEvent: "tool.started",
      liveSteps: [
        {
          step_id: "live_run_created_0",
          step_type: "run",
          status: "running",
          payload: { event_type: "run.created" },
        },
        {
          step_id: "live_tool_started_1",
          step_type: "tool:diagnostic.check",
          status: "running",
          payload: { event_type: "tool.started" },
        },
      ],
    });
  });

  it("extracts a live run from reasoning process text", () => {
    const artifact = extractRuntimeArtifactFromMessages([
      {
        role: "assistant",
        content: [
          {
            type: "reasoning",
            text: "runtime.stream.opening\nrun.created · run_abcdef123456\nmodel.started · run_abcdef123456\n",
          },
        ],
      },
    ]);

    expect(artifact).toEqual({
      title: "Agent 正在运行",
      summary: "调用模型",
      auditEventId: undefined,
      events: ["run.created", "model.started"],
      toolName: "通用 Agent",
      artifactId: undefined,
      runId: "run_abcdef123456",
      status: "running",
      latestEvent: "model.started",
      liveSteps: [
        {
          step_id: "live_run_created_0",
          step_type: "run",
          status: "running",
          payload: { event_type: "run.created" },
        },
        {
          step_id: "live_model_started_1",
          step_type: "model",
          status: "running",
          payload: { event_type: "model.started" },
        },
      ],
    });
  });

  it("marks an unfinished running artifact as cancelled after the thread stops", () => {
    const artifact = normalizeRuntimeArtifactForThreadState({
      title: "Agent 正在运行",
      summary: "当前事件：model.started",
      auditEventId: undefined,
      events: ["run.created", "model.started"],
      toolName: "通用 Agent",
      artifactId: undefined,
      runId: "run_abcdef123456",
      status: "running",
      latestEvent: "model.started",
    }, false);

    expect(artifact).toMatchObject({
      title: "Agent 已停止",
      summary: "用户已停止生成，最后事件：model.started",
      status: "cancelled",
      runId: "run_abcdef123456",
    });
  });
});
