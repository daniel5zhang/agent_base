"use client";

import { useState } from "react";
import { AssistantRuntimeProvider, useAuiState } from "@assistant-ui/react";
import {
  useChatRuntime,
  AssistantChatTransport,
} from "@assistant-ui/react-ai-sdk";
import { Thread } from "@/components/assistant-ui/thread";
import { WorkbenchShell, type RuntimeArtifact, type RunStepRow } from "@/features/workbench/workbench-shell";

type AssistantMessageLike = {
  role: string;
  content: ReadonlyArray<{
    type: string;
    toolName?: string;
    result?: unknown;
    data?: unknown;
    text?: string;
  }>;
};

type ToolResultLike = {
  title?: string;
  summary?: string;
  audit_event_id?: string;
  events?: string[];
  artifact_id?: string;
  run_id?: string;
};

type RuntimeDataLike = {
  title?: string;
  summary?: string;
  auditEventId?: string;
  audit_event_id?: string;
  events?: string[];
  artifactId?: string;
  artifact_id?: string;
  runId?: string;
  run_id?: string;
  toolName?: string;
  tool_name?: string;
  status?: string;
  eventType?: string;
  event_type?: string;
  liveSteps?: RunStepRow[];
  live_steps?: RunStepRow[];
};

function normalizeEventStepStatus(eventType: string, runtimeStatus?: string) {
  if (eventType.endsWith(".failed")) return "failed";
  if (eventType.endsWith(".cancelled")) return "cancelled";
  if (eventType.endsWith(".started") || eventType === "run.created" || runtimeStatus === "running") return "running";
  return runtimeStatus ?? "completed";
}

function normalizeEventStepType(eventType: string, runtimeData?: RuntimeDataLike) {
  if (eventType.startsWith("tool.")) {
    const toolName = runtimeData?.toolName ?? runtimeData?.tool_name ?? "unknown";
    return `tool:${toolName}`;
  }
  if (eventType.startsWith("model.")) return "model";
  if (eventType.startsWith("run.")) return "run";
  return eventType.split(".")[0] || "runtime";
}

function runtimeEventLabel(eventType: string) {
  const labels: Record<string, string> = {
    "run.created": "创建运行",
    "intent.classified": "识别意图",
    "context.built": "准备上下文",
    "model.started": "调用模型",
    "model.completed": "模型返回",
    "tool.started": "调用工具",
    "tool.completed": "工具完成",
    "artifact.created": "生成 Artifact",
    "run.completed": "完成运行",
    "run.failed": "运行失败",
    "run.cancelled": "运行已取消",
  };
  return labels[eventType] ?? eventType;
}

function runtimeDataToLiveStep(runtimeData: RuntimeDataLike, index: number): RunStepRow | undefined {
  const eventType = runtimeData.eventType ?? runtimeData.event_type;
  if (!eventType) return undefined;
  return {
    step_id: `live_${eventType.replace(/[^a-z0-9]+/gi, "_")}_${index}`,
    step_type: normalizeEventStepType(eventType, runtimeData),
    status: normalizeEventStepStatus(eventType, runtimeData.status),
    payload: { event_type: eventType },
  };
}

export function extractRuntimeArtifactFromMessages(messages: ReadonlyArray<AssistantMessageLike>): RuntimeArtifact | undefined {
  const assistantMessages = [...messages]
    .reverse()
    .filter((message) => message.role === "assistant");

  for (const message of assistantMessages) {
    const toolPart = [...message.content]
      .reverse()
      .find((part) => part.type === "tool-call" && part.toolName);
    if (toolPart) {
      const output = toolPart.result as ToolResultLike | undefined;
      if (output?.title && output.summary && output.audit_event_id) {
        return {
          title: output.title,
          summary: output.summary,
          auditEventId: output.audit_event_id,
          events: output.events ?? [],
          toolName: toolPart.toolName ?? "通用 Agent",
          artifactId: output.artifact_id,
          runId: output.run_id,
          status: undefined,
          latestEvent: undefined,
        };
      }
    }

    const runtimeParts = message.content
      .filter((part) => part.type === "data-runtime" && part.data);
    const runtimePart = [...runtimeParts].reverse().find((part) => part.data);
    const runtimeData = runtimePart?.data as RuntimeDataLike | undefined;
    if (runtimeData?.runId || runtimeData?.run_id) {
      const status = runtimeData.status;
      const eventType = runtimeData.eventType ?? runtimeData.event_type;
      const runId = runtimeData.runId ?? runtimeData.run_id;
      const liveSteps = [
        ...(runtimeData.liveSteps ?? runtimeData.live_steps ?? []),
        ...runtimeParts
          .map((part) => part.data as RuntimeDataLike)
          .filter((partData) => (partData.runId ?? partData.run_id) === runId)
          .map((partData, index) => runtimeDataToLiveStep(partData, index))
          .filter((step): step is RunStepRow => Boolean(step)),
      ];
      return {
        title: runtimeData.title ?? (status === "running" ? "Agent 正在运行" : "Agent 运行"),
        summary: runtimeData.summary ?? (eventType ? runtimeEventLabel(eventType) : "正在同步运行证据"),
        auditEventId: runtimeData.auditEventId ?? runtimeData.audit_event_id,
        events: runtimeData.events ?? (eventType ? [eventType] : []),
        toolName: runtimeData.toolName ?? runtimeData.tool_name ?? "通用 Agent",
        artifactId: runtimeData.artifactId ?? runtimeData.artifact_id,
        runId,
        status,
        latestEvent: eventType,
        liveSteps: liveSteps.length > 0 ? liveSteps : undefined,
      };
    }

    const reasoningPart = [...message.content]
      .reverse()
      .find((part) => part.type === "reasoning" && part.text);
    const reasoningText = reasoningPart?.text ?? "";
    const runId = reasoningText.match(/run_[a-f0-9]+/)?.[0];
    if (runId) {
      const eventMatches = [...reasoningText.matchAll(/(?:^|\n)([a-z_]+\.[a-z_]+)/g)]
        .map((match) => match[1])
        .filter((event) => event !== "runtime.stream");
      const latestEvent = eventMatches.at(-1);
      const status = latestEvent === "run.cancelled"
        ? "cancelled"
        : latestEvent === "run.completed"
          ? "completed"
          : latestEvent === "run.failed"
            ? "failed"
            : "running";
      return {
        title: status === "running" ? "Agent 正在运行" : "Agent 运行",
        summary: latestEvent ? runtimeEventLabel(latestEvent) : "正在同步运行证据",
        auditEventId: undefined,
        events: eventMatches,
        toolName: "通用 Agent",
        artifactId: undefined,
        runId,
        status,
        latestEvent,
        liveSteps: eventMatches
          .map((eventType, index) => runtimeDataToLiveStep({ eventType, status }, index))
          .filter((step): step is RunStepRow => Boolean(step)),
      };
    }
  }

  return undefined;
}

export function normalizeRuntimeArtifactForThreadState(
  runtimeArtifact: RuntimeArtifact | undefined,
  threadIsRunning: boolean,
): RuntimeArtifact | undefined {
  if (runtimeArtifact?.status !== "running" || threadIsRunning) {
    return runtimeArtifact;
  }
  return {
    ...runtimeArtifact,
    title: "Agent 已停止",
    summary: runtimeArtifact.latestEvent
      ? `用户已停止生成，最后事件：${runtimeArtifact.latestEvent}`
      : "用户已停止生成。",
    status: "cancelled",
  };
}

export const Assistant = () => {
  const [threadSession, setThreadSession] = useState(0);
  const [activeThreadId, setActiveThreadId] = useState<string | undefined>();

  return (
    <AssistantSession
      key={`${threadSession}:${activeThreadId ?? "new"}`}
      activeThreadId={activeThreadId}
      onSelectThread={setActiveThreadId}
      onNewThread={() => {
        setActiveThreadId(undefined);
        setThreadSession((value) => value + 1);
      }}
    />
  );
};

function AssistantSession({
  activeThreadId,
  onSelectThread,
  onNewThread,
}: {
  activeThreadId?: string;
  onSelectThread: (threadId: string | undefined) => void;
  onNewThread: () => void;
}) {
  const runtime = useChatRuntime({
    transport: new AssistantChatTransport({
      api: activeThreadId ? `/api/chat?thread_id=${encodeURIComponent(activeThreadId)}` : "/api/chat",
    }),
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <WorkbenchRuntimeShell
        activeThreadId={activeThreadId}
        onSelectThread={onSelectThread}
        onNewThread={onNewThread}
      />
    </AssistantRuntimeProvider>
  );
}

function WorkbenchRuntimeShell({
  activeThreadId,
  onSelectThread,
  onNewThread,
}: {
  activeThreadId?: string;
  onSelectThread: (threadId: string | undefined) => void;
  onNewThread: () => void;
}) {
  const threadIsRunning = useAuiState((state) => state.thread.isRunning);
  const runtimeArtifactValue = useAuiState((state) => {
    const artifact = extractRuntimeArtifactFromMessages(state.thread.messages);
    return artifact ? JSON.stringify(artifact) : undefined;
  });

  const runtimeArtifact = runtimeArtifactValue
    ? JSON.parse(runtimeArtifactValue) as {
        title: string;
        summary: string;
        auditEventId: string;
        events: string[];
        toolName: string;
        artifactId?: string;
        runId?: string;
        status?: string;
        latestEvent?: string;
        liveSteps?: RunStepRow[];
    }
    : undefined;

  const normalizedRuntimeArtifact = normalizeRuntimeArtifactForThreadState(runtimeArtifact, threadIsRunning);

  return (
    <WorkbenchShell
      runtimeArtifact={normalizedRuntimeArtifact}
      activeThreadId={activeThreadId}
      renderThread={({ historyHeader, historyMessages }) => (
        <Thread
          historyHeader={historyHeader}
          historyMessages={historyMessages}
          suppressWelcome={Boolean(activeThreadId)}
        />
      )}
      onSelectThread={onSelectThread}
      onNewThread={onNewThread}
    />
  );
}
