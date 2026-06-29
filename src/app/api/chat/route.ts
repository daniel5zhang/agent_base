import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  type UIMessage,
} from "ai";

type IncomingBody = {
  messages?: UIMessage[];
  thread_id?: string;
};

type StreamWriter = Parameters<Parameters<typeof createUIMessageStream>[0]["execute"]>[0]["writer"];

type AgentRunResponse = {
  run_id: string;
  thread_id: string;
  workspace_id: string;
  status: "completed" | "blocked" | "failed" | "cancelled";
  intent: string;
  response: string;
  tool_invocations: string[];
  artifacts: Array<{
    artifact_id: string;
    artifact_type: string;
    title: string;
  }>;
  memory_ids: string[];
  audit_event_id: string;
  events: string[];
};

type RuntimeEventPayload = {
  event_id?: string;
  event_type: string;
  run_id?: string;
  thread_id?: string;
  workspace_id?: string;
  payload_digest?: string;
  occurred_at?: string;
  payload?: {
    delta?: string;
    tool_id?: string;
    [key: string]: unknown;
  };
};

type RuntimeData = {
  runId?: string;
  status: "running" | "completed" | "blocked" | "failed" | "cancelled";
  title: string;
  summary: string;
  eventType?: string;
  auditEventId?: string;
  toolName?: string;
  artifactId?: string;
  events?: string[];
};

type ServerSentEvent = {
  event: string;
  data: unknown;
};

class UserCancelledRunError extends Error {
  constructor() {
    super("user_cancelled");
    this.name = "UserCancelledRunError";
  }
}

function getMessageText(message: UIMessage | undefined) {
  if (!message) return "";
  return message.parts
    ?.map((part) => (part.type === "text" ? part.text : ""))
    .join("")
    .trim() ?? "";
}

function normalizeThreadId(threadId: string | undefined) {
  const normalized = threadId?.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 64);
  return normalized || undefined;
}

function threadIdFromMessages(messages: UIMessage[], explicitThreadId?: string) {
  const normalizedExplicitThreadId = normalizeThreadId(explicitThreadId);
  if (normalizedExplicitThreadId) return normalizedExplicitThreadId;
  const firstMessageId = messages.find((message) => typeof message.id === "string" && message.id.length > 0)?.id;
  if (!firstMessageId) return "thread_default";
  const normalized = firstMessageId.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 64);
  return normalized ? `thread_${normalized}` : "thread_default";
}

function writeText(writer: StreamWriter, id: string, text: string) {
  writer.write({ type: "text-start", id });
  writer.write({ type: "text-delta", id, delta: text });
  writer.write({ type: "text-end", id });
}

function startText(writer: StreamWriter, id: string) {
  writer.write({ type: "text-start", id });
}

function appendText(writer: StreamWriter, id: string, text: string) {
  writer.write({ type: "text-delta", id, delta: text });
}

function endText(writer: StreamWriter, id: string) {
  writer.write({ type: "text-end", id });
}

function writeReasoning(writer: StreamWriter, id: string, text: string) {
  writer.write({ type: "reasoning-start", id });
  writer.write({ type: "reasoning-delta", id, delta: text });
  writer.write({ type: "reasoning-end", id });
}

function writeRuntimeData(writer: StreamWriter, data: RuntimeData) {
  writer.write({
    type: "data-runtime",
    id: data.runId ? `runtime_${data.runId}` : "runtime_pending",
    data,
  });
}

function startReasoning(writer: StreamWriter, id: string) {
  writer.write({ type: "reasoning-start", id });
}

function appendReasoning(writer: StreamWriter, id: string, text: string) {
  writer.write({ type: "reasoning-delta", id, delta: text });
}

function endReasoning(writer: StreamWriter, id: string) {
  writer.write({ type: "reasoning-end", id });
}

function workbenchServerUrl() {
  return (process.env.WORKBENCH_SERVER_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

function primaryToolName(toolInvocations: string[]) {
  return toolInvocations.find((tool) => tool !== "intent.classify" && tool !== "artifact.create") ?? "conversation.respond";
}

function toolTitle(toolName: string) {
  const titles: Record<string, string> = {
    "plan.update": "计划工具",
    "memory.write": "记忆工具",
    "memory.read": "记忆读取工具",
    "workspace.list": "工作空间工具",
    "workspace.read": "文件读取工具",
    "settings.read": "设置工具",
    "diagnostic.check": "诊断工具",
    "local_data.analyze": "本地分析工具",
    "artifact.update": "Artifact 更新工具",
    "plugin.catalog": "插件目录",
    "conversation.respond": "通用对话",
  };
  return titles[toolName] ?? toolName;
}

function artifactSummary(result: AgentRunResponse) {
  if (result.artifacts[0]?.artifact_type === "plan") return "已生成计划";
  if (result.artifacts[0]?.artifact_type === "workspace_listing") return "已生成工作空间文件列表";
  if (result.artifacts[0]?.artifact_type === "file_preview") return "已生成文件预览";
  if (result.artifacts[0]?.artifact_type === "settings_snapshot") return "已生成设置快照";
  if (result.artifacts[0]?.artifact_type === "diagnostic_report") return "已生成诊断报告";
  if (result.artifacts[0]?.artifact_type === "local_data_analysis") return "已生成本地数据分析";
  if (result.artifacts[0]?.artifact_type === "updated_artifact") return "已更新 Artifact";
  if (result.artifacts[0]?.artifact_type === "memory_snapshot") return "已读取受控记忆";
  if (result.memory_ids.length > 0) return "已写入受控记忆";
  if (result.status === "blocked") return "当前阶段暂未启用该业务能力";
  return "已完成通用 Agent 运行";
}

function runtimeEventLabel(eventType: string) {
  const labels: Record<string, string> = {
    "runtime.stream.opening": "连接 Agent 运行时",
    "run.created": "创建运行",
    "message.received": "接收用户消息",
    "intent.classified": "识别意图",
    "context.built": "准备上下文",
    "tool.planned": "规划工具",
    "model.selected": "选择模型",
    "model.started": "调用模型",
    "model.tool_calls.requested": "模型请求工具调用",
    "model.completed": "模型返回",
    "tool.started": "调用工具",
    "tool.batch.started": "开始执行工具",
    "tool.completed": "工具完成",
    "artifact.created": "生成 Artifact",
    "run.completed": "完成运行",
    "run.failed": "运行失败",
    "run.blocked": "请求被阻断",
    "run.cancelled": "运行已取消",
  };
  return labels[eventType] ?? eventType;
}

async function openServerAgentStream(question: string, threadId: string): Promise<ReadableStream<Uint8Array>> {
  const response = await fetch(`${workbenchServerUrl()}/api/agent/run/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      tenant_id: "tenant_demo",
      workspace_id: "workspace_default",
      thread_id: threadId,
      user_id: "user_demo",
      message: question,
    }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`Workbench server /api/agent/run/stream failed: ${response.status}`);
  }
  return response.body;
}

async function cancelServerRun(runId: string) {
  await fetch(`${workbenchServerUrl()}/api/runs/${runId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: "user_demo", reason: "用户停止生成" }),
  }).catch(() => undefined);
}

function parseSseChunk(buffer: string): { events: ServerSentEvent[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events = parts
    .map((part) => {
      const eventLine = part.split("\n").find((line) => line.startsWith("event: "));
      const dataLines = part.split("\n").filter((line) => line.startsWith("data: "));
      if (!eventLine || dataLines.length === 0) return undefined;
      const event = eventLine.slice("event: ".length).trim();
      const dataText = dataLines.map((line) => line.slice("data: ".length)).join("\n");
      try {
        return { event, data: JSON.parse(dataText) };
      } catch {
        return { event, data: dataText };
      }
    })
    .filter((event): event is ServerSentEvent => Boolean(event));
  return { events, rest };
}

function writeToolOutput(writer: StreamWriter, question: string, result: AgentRunResponse) {
  const toolName = primaryToolName(result.tool_invocations);
  if (toolName === "conversation.respond") return;
  const toolCallId = `tool_${toolName.replaceAll(".", "_")}_${result.run_id}`;
  writer.write({
    type: "tool-input-available",
    toolCallId,
    toolName,
    title: toolTitle(toolName),
    input: {
      message: question,
      workspace_id: result.workspace_id,
    },
  });
  writer.write({
    type: "tool-output-available",
    toolCallId,
    output: {
      status: result.status,
      intent: result.intent,
      artifact_type: result.artifacts[0]?.artifact_type,
      artifact_id: result.artifacts[0]?.artifact_id,
      run_id: result.run_id,
      title: result.artifacts[0]?.title ?? toolTitle(toolName),
      summary: artifactSummary(result),
      events: result.events,
      memory_ids: result.memory_ids,
      audit_event_id: result.audit_event_id,
    },
  });
}

async function consumeServerAgentStream(
  question: string,
  threadId: string,
  writer: StreamWriter,
  reasoningId: string,
  signal?: AbortSignal,
): Promise<{ result: AgentRunResponse; streamedText: boolean }> {
  const body = await openServerAgentStream(question, threadId);
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: AgentRunResponse | undefined;
  let streamedText = false;
  let textStarted = false;
  let currentRunId: string | undefined;
  let cancelPromise: Promise<void> | undefined;
  const streamingAnswerId = "answer_streaming_model";
  const abortListener = () => {
    if (currentRunId) {
      cancelPromise = cancelServerRun(currentRunId);
    }
    void reader.cancel("user_cancelled").catch(() => undefined);
  };

  if (signal?.aborted) {
    abortListener();
  } else {
    signal?.addEventListener("abort", abortListener, { once: true });
  }

  try {
    while (true) {
      if (signal?.aborted) {
        throw new UserCancelledRunError();
      }
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseChunk(buffer);
      buffer = parsed.rest;
      for (const event of parsed.events) {
      if (event.event === "runtime_event") {
        const runtimeEvent = event.data as RuntimeEventPayload;
        currentRunId = runtimeEvent.run_id ?? currentRunId;
        appendReasoning(writer, reasoningId, `- ${runtimeEventLabel(runtimeEvent.event_type)}\n`);
        if (currentRunId) {
          writeRuntimeData(writer, {
            runId: currentRunId,
            status: runtimeEvent.event_type === "run.cancelled" ? "cancelled" : "running",
            title: "Agent 正在运行",
            summary: runtimeEventLabel(runtimeEvent.event_type),
            eventType: runtimeEvent.event_type,
            toolName: runtimeEvent.payload?.tool_id,
            events: [runtimeEvent.event_type],
          });
        }
      }
        if (event.event === "model_delta") {
          const runtimeEvent = event.data as RuntimeEventPayload;
          currentRunId = runtimeEvent.run_id ?? currentRunId;
          const delta = runtimeEvent.payload?.delta ?? "";
          if (delta) {
            if (!textStarted) {
              startText(writer, streamingAnswerId);
              textStarted = true;
            }
            appendText(writer, streamingAnswerId, delta);
            streamedText = true;
          }
        }
      if (event.event === "final_result") {
        finalResult = event.data as AgentRunResponse;
        currentRunId = finalResult.run_id;
        appendReasoning(writer, reasoningId, `- ${runtimeEventLabel(`run.${finalResult.status}`)}\n`);
        writeRuntimeData(writer, {
          runId: finalResult.run_id,
          status: finalResult.status,
          title: finalResult.artifacts[0]?.title ?? toolTitle(primaryToolName(finalResult.tool_invocations)),
          summary: artifactSummary(finalResult),
          auditEventId: finalResult.audit_event_id,
          toolName: primaryToolName(finalResult.tool_invocations),
          artifactId: finalResult.artifacts[0]?.artifact_id,
          events: finalResult.events,
        });
      }
        if (event.event === "run_error") {
          const data = event.data as { message?: string };
          throw new Error(data.message ?? "run_error");
        }
      }
    }
  } finally {
    signal?.removeEventListener("abort", abortListener);
    if (signal?.aborted && currentRunId && !cancelPromise) {
      cancelPromise = cancelServerRun(currentRunId);
    }
    await cancelPromise;
  }

  if (signal?.aborted) {
    throw new UserCancelledRunError();
  }
  if (!finalResult) {
    throw new Error("missing_final_result");
  }
  if (textStarted) {
    endText(writer, streamingAnswerId);
  }
  return { result: finalResult, streamedText };
}

export async function POST(req: Request) {
  const body = (await req.json()) as IncomingBody;
  const url = new URL(req.url);
  const messages = body.messages ?? [];
  const question = getMessageText(messages.at(-1));
  const threadId = threadIdFromMessages(messages, body.thread_id ?? url.searchParams.get("thread_id") ?? undefined);

  const stream = createUIMessageStream({
    originalMessages: messages,
    execute: async ({ writer }) => {
      writer.write({ type: "start" });
      writer.write({ type: "start-step" });

      try {
        const reasoningId = "reasoning_runtime";
        startReasoning(writer, reasoningId);
        appendReasoning(writer, reasoningId, `- ${runtimeEventLabel("runtime.stream.opening")}\n`);
        const { result, streamedText } = await consumeServerAgentStream(question, threadId, writer, reasoningId, req.signal);
        endReasoning(writer, reasoningId);
        writeToolOutput(writer, question, result);
        if (!streamedText) {
          writeText(writer, `answer_${result.intent}`, result.response);
        }
      } catch (error) {
        if (error instanceof UserCancelledRunError || req.signal.aborted) {
          return;
        }
        const message = error instanceof Error ? error.message : "unknown_error";
        writeReasoning(writer, "reasoning_error", `运行失败：${message}\n`);
        writeText(writer, "answer_error", `服务端不可用或运行失败：${message}。请检查 Python 服务端和模型配置后重试。`);
      }

      writer.write({ type: "finish-step" });
      writer.write({ type: "finish", finishReason: "stop" });
    },
  });

  return createUIMessageStreamResponse({ stream });
}
