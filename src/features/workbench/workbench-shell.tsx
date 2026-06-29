"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  BadgeCheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  FileClockIcon,
  ListChecksIcon,
  MessageSquareIcon,
  PanelRightIcon,
  RotateCcwIcon,
  SettingsIcon,
  ShieldCheckIcon,
  WrenchIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export type RuntimeArtifact = {
  title: string;
  summary: string;
  auditEventId?: string;
  events: string[];
  toolName: string;
  artifactId?: string;
  runId?: string;
  status?: string;
  latestEvent?: string;
  liveSteps?: RunStepRow[];
};

export type DiagnosticsState = {
  status: string;
  phase: string;
  checks: Record<string, string>;
};

type WorkbenchShellProps = {
  thread?: ReactNode;
  renderThread?: (slots: { historyHeader?: ReactNode; historyMessages?: ReactNode }) => ReactNode;
  runtimeArtifact?: RuntimeArtifact;
  activeThreadId?: string;
  onSelectThread?: (threadId: string | undefined) => void;
  onNewThread?: () => void;
};

type ModelCatalog = {
  models: Array<{
    model_id: string;
    provider: string;
    base_url: string;
    configured: boolean;
    capabilities: string[];
  }>;
};

type RuntimeEventRow = {
  event_id: string;
  event_type: string;
  payload_digest: string;
  occurred_at?: string;
};

type ThreadRow = {
  thread_id: string;
  title: string;
  workspace_id: string;
  last_message: string;
  message_count: number;
};

type ThreadMessageRow = {
  message_id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  run_id?: string | null;
  created_at?: string | null;
};

type ThreadDetail = {
  thread: {
    thread_id: string;
    title: string;
    workspace_id: string;
    created_at?: string | null;
  };
  messages: ThreadMessageRow[];
};

export type RunStepRow = {
  step_id: string;
  step_type: string;
  status: string;
  payload?: Record<string, unknown>;
};

type RunEvidence = {
  events: RuntimeEventRow[];
  eventsStatus?: string;
  steps: RunStepRow[];
  stepsStatus?: string;
};

function useRunEvidence(runId: string | undefined, refreshKey: string | undefined): RunEvidence {
  const [runtimeEvents, setRuntimeEvents] = useState<RuntimeEventRow[]>([]);
  const [runtimeEventsStatus, setRuntimeEventsStatus] = useState<string | undefined>();
  const [runSteps, setRunSteps] = useState<RunStepRow[]>([]);
  const [runStepsStatus, setRunStepsStatus] = useState<string | undefined>();

  useEffect(() => {
    if (!runId) {
      Promise.resolve().then(() => {
        setRuntimeEvents([]);
        setRuntimeEventsStatus(undefined);
        setRunSteps([]);
        setRunStepsStatus(undefined);
      });
      return;
    }
    let cancelled = false;
    Promise.resolve().then(() => {
      if (!cancelled) {
        setRuntimeEventsStatus("正在同步运行事件...");
        setRunStepsStatus("正在同步执行步骤...");
      }
    });
    Promise.allSettled([
      fetch(`/api/runs/${runId}`)
        .then((response) => {
          if (!response.ok) throw new Error(`http_${response.status}`);
          return response.json() as Promise<{ steps?: RunStepRow[] }>;
        }),
      fetch(`/api/runs/${runId}/events`)
        .then((response) => {
          if (!response.ok) throw new Error(`http_${response.status}`);
          return response.json() as Promise<{ events: RuntimeEventRow[] }>;
        }),
    ]).then(([runResult, eventsResult]) => {
      if (cancelled) return;
      if (runResult.status === "fulfilled") {
        const steps = runResult.value.steps ?? [];
        setRunSteps(steps);
        setRunStepsStatus(`已同步 ${steps.length} 个执行步骤`);
      } else {
        setRunSteps([]);
        setRunStepsStatus(`执行步骤同步失败：${runResult.reason instanceof Error ? runResult.reason.message : "unknown_error"}`);
      }
      if (eventsResult.status === "fulfilled") {
        setRuntimeEvents(eventsResult.value.events);
        setRuntimeEventsStatus(`已同步 ${eventsResult.value.events.length} 条运行事件`);
      } else {
        setRuntimeEvents([]);
        setRuntimeEventsStatus(`运行事件同步失败：${eventsResult.reason instanceof Error ? eventsResult.reason.message : "unknown_error"}`);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [runId, refreshKey]);

  return {
    events: runtimeEvents,
    eventsStatus: runtimeEventsStatus,
    steps: runSteps,
    stepsStatus: runStepsStatus,
  };
}

function useRecentThreads(): { threads: ThreadRow[]; status?: string } {
  const [threads, setThreads] = useState<ThreadRow[]>([]);
  const [status, setStatus] = useState<string | undefined>("正在读取最近会话...");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/threads?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo")
      .then((response) => {
        if (!response.ok) throw new Error(`http_${response.status}`);
        return response.json() as Promise<{ threads: ThreadRow[] }>;
      })
      .then((body) => {
        if (cancelled) return;
        setThreads(body.threads);
        setStatus(body.threads.length > 0 ? undefined : "暂无会话");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setThreads([]);
        setStatus(`最近会话读取失败：${error instanceof Error ? error.message : "unknown_error"}`);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { threads, status };
}

function useThreadDetail(threadId: string | undefined): { detail?: ThreadDetail; status?: string } {
  const [detail, setDetail] = useState<ThreadDetail | undefined>();
  const [status, setStatus] = useState<string | undefined>();

  useEffect(() => {
    if (!threadId) {
      Promise.resolve().then(() => {
        setDetail(undefined);
        setStatus(undefined);
      });
      return;
    }
    let cancelled = false;
    Promise.resolve().then(() => {
      if (!cancelled) setStatus("正在加载会话...");
    });
    fetch(`/api/threads/${encodeURIComponent(threadId)}?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo`)
      .then((response) => {
        if (!response.ok) throw new Error(`http_${response.status}`);
        return response.json() as Promise<ThreadDetail>;
      })
      .then((body) => {
        if (cancelled) return;
        setDetail(body);
        setStatus(undefined);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setDetail(undefined);
        setStatus(`会话加载失败：${error instanceof Error ? error.message : "unknown_error"}`);
      });
    return () => {
      cancelled = true;
    };
  }, [threadId]);

  return { detail, status };
}

function WorkbenchSidebar({
  onOpenSettings,
  selectedThreadId,
  onSelectThread,
  onNewThread,
}: {
  onOpenSettings: () => void;
  selectedThreadId?: string;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
}) {
  const recentThreads = useRecentThreads();

  return (
    <Sidebar role="navigation" aria-label="工作台导航" collapsible="icon" variant="sidebar">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" isActive tooltip="企业 Agent 工作台">
              <div className="flex size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <BadgeCheckIcon aria-hidden="true" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">企业 Agent 工作台</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarSeparator />

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="新建任务" onClick={onNewThread} isActive={!selectedThreadId}>
                  <MessageSquareIcon aria-hidden="true" />
                  <span>新建任务</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>最近会话</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {recentThreads.threads.length > 0 ? recentThreads.threads.map((thread) => (
                <SidebarMenuItem key={thread.thread_id}>
                  <SidebarMenuButton
                    tooltip={thread.title}
                    className="h-auto items-start py-2"
                    isActive={selectedThreadId === thread.thread_id}
                    onClick={() => onSelectThread(thread.thread_id)}
                  >
                    <MessageSquareIcon aria-hidden="true" />
                    <span className="grid min-w-0 gap-0.5">
                      <span className="truncate font-medium">{thread.title}</span>
                      <span className="truncate text-xs text-muted-foreground">
                        {thread.message_count} 条消息
                      </span>
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )) : (
                <SidebarMenuItem>
                  <SidebarMenuButton disabled className="h-auto items-start py-2">
                    <MessageSquareIcon aria-hidden="true" />
                    <span className="truncate text-xs text-muted-foreground">
                      {recentThreads.status ?? "暂无会话"}
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

      </SidebarContent>

      <SidebarFooter>
        <SidebarSeparator />
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="设置与模型" onClick={onOpenSettings}>
              <SettingsIcon aria-hidden="true" />
              <span>设置与模型</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}

function RuntimeInspector({
  runtimeArtifact,
  evidence,
  onCollapse,
}: {
  runtimeArtifact?: RuntimeArtifact;
  evidence: RunEvidence;
  onCollapse: () => void;
}) {
  const fallbackEvents = runtimeArtifact?.events?.length
    ? runtimeArtifact.events
    : ["run.created", "intent.classified", "context.built", "model.completed"];
  const visibleSteps = evidence.steps.length > 0
    ? evidence.steps
    : runtimeArtifact?.liveSteps ?? [
      { step_id: "fallback-run", step_type: "run", status: runtimeArtifact?.status ?? "waiting" },
    ];
  const visibleStepsStatus = evidence.steps.length > 0
    ? evidence.stepsStatus
    : runtimeArtifact?.liveSteps?.length
      ? `已接收 ${runtimeArtifact.liveSteps.length} 个实时步骤`
      : evidence.stepsStatus;
  const [diagnostics, setDiagnostics] = useState<DiagnosticsState | undefined>();
  const [diagnosticsError, setDiagnosticsError] = useState<string | undefined>();
  const [runActionStatus, setRunActionStatus] = useState<string | undefined>();

  useEffect(() => {
    let cancelled = false;
    fetch("/api/diagnostics")
      .then((response) => {
        if (!response.ok) throw new Error(`http_${response.status}`);
        return response.json() as Promise<DiagnosticsState>;
      })
      .then((body) => {
        if (!cancelled) setDiagnostics(body);
      })
      .catch((error: unknown) => {
        if (!cancelled) setDiagnosticsError(error instanceof Error ? error.message : "unknown_error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function cancelRun() {
    if (!runtimeArtifact?.runId) return;
    const response = await fetch(`/api/runs/${runtimeArtifact.runId}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: "user_demo", reason: "用户取消" }),
    });
    const body = await response.json() as { run_id?: string; status?: string };
    setRunActionStatus(body.status === "cancelled" && body.run_id
      ? `运行已取消：${body.run_id}`
      : "取消运行失败");
  }

  async function retryRun() {
    if (!runtimeArtifact?.runId) return;
    const response = await fetch(`/api/runs/${runtimeArtifact.runId}/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: "user_demo" }),
    });
    const body = await response.json() as { run_id?: string; status?: string };
    setRunActionStatus(body.status === "created" && body.run_id
      ? `已创建重试运行：${body.run_id}`
      : "重试运行失败");
  }

  return (
    <aside aria-label="运行证据面板" className="hidden min-w-0 border-l bg-background lg:flex lg:w-[380px] lg:flex-col">
      <div className="flex h-14 shrink-0 items-center justify-between border-b px-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <PanelRightIcon aria-hidden="true" />
            运行证据
          </div>
          <div className="text-xs text-muted-foreground">Artifact / Runtime Event / 诊断</div>
        </div>
        <Button variant="ghost" size="icon" className="size-8 rounded-full" onClick={onCollapse} aria-label="收起运行证据">
          <ChevronRightIcon aria-hidden="true" className="size-4" />
        </Button>
      </div>

      <Tabs defaultValue="artifact" className="min-h-0 flex-1 gap-0">
        <div className="border-b px-4 py-3">
          <TabsList variant="line" className="w-full justify-start">
            <TabsTrigger value="artifact">Artifact</TabsTrigger>
            <TabsTrigger value="events">事件</TabsTrigger>
            <TabsTrigger value="diagnostics">诊断</TabsTrigger>
          </TabsList>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          <TabsContent value="artifact" className="flex flex-col gap-4 p-4">
            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ListChecksIcon aria-hidden="true" />
                  {runtimeArtifact?.title ?? "等待 Agent 运行"}
                </CardTitle>
                <CardAction>
                  <div className="flex flex-wrap justify-end gap-2">
                    {runtimeArtifact?.status ? (
                      <Badge variant={runtimeArtifact.status === "running" ? "default" : "secondary"}>
                        {runtimeArtifact.status === "running" ? "运行中" : runtimeArtifact.status}
                      </Badge>
                    ) : null}
                    <Badge variant="secondary">{runtimeArtifact?.toolName ?? "通用 Agent"}</Badge>
                  </div>
                </CardAction>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {runtimeArtifact?.summary ?? "Agent 运行后，这里展示 Artifact、事件和诊断信息。"}
                </p>
                {runtimeArtifact?.artifactId || runtimeArtifact?.runId || runtimeArtifact?.latestEvent ? (
                  <dl className="mt-4 grid grid-cols-[76px_1fr] gap-x-3 gap-y-2 text-xs">
                    {runtimeArtifact.artifactId ? (
                      <>
                        <dt className="text-muted-foreground">Artifact</dt>
                        <dd><code>{runtimeArtifact.artifactId}</code></dd>
                      </>
                    ) : null}
                    {runtimeArtifact.runId ? (
                      <>
                        <dt className="text-muted-foreground">Run</dt>
                        <dd><code>{runtimeArtifact.runId}</code></dd>
                      </>
                    ) : null}
                    {runtimeArtifact.latestEvent ? (
                      <>
                        <dt className="text-muted-foreground">事件</dt>
                        <dd><code>{runtimeArtifact.latestEvent}</code></dd>
                      </>
                    ) : null}
                  </dl>
                ) : null}
                {runtimeArtifact?.runId ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={cancelRun}>取消运行</Button>
                    <Button variant="secondary" size="sm" onClick={retryRun}>重试运行</Button>
                  </div>
                ) : null}
                {runActionStatus ? (
                  <p className="mt-3 text-xs text-muted-foreground">{runActionStatus}</p>
                ) : null}
              </CardContent>
            </Card>

            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileClockIcon aria-hidden="true" />
                  审计编号
                </CardTitle>
                <CardDescription>记录本次 Agent 运行的审计标识。</CardDescription>
              </CardHeader>
              <CardContent>
                <code className="block rounded-lg bg-muted px-3 py-2 font-mono text-xs text-muted-foreground">
                  {runtimeArtifact?.auditEventId ?? "等待运行后生成 audit_event_id"}
                </code>
              </CardContent>
            </Card>

            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldCheckIcon aria-hidden="true" />
                  运行边界
                </CardTitle>
                <CardDescription>当前只执行通用 Agent 能力；业务插件执行将在后续阶段接入。</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                <Badge variant="secondary">内置工具可用</Badge>
                <Badge variant="outline">业务插件待接入</Badge>
                <Badge variant="outline">不伪造业务结果</Badge>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="events" className="flex flex-col gap-4 p-4">
            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ListChecksIcon aria-hidden="true" />
                  执行步骤
                </CardTitle>
                <CardDescription>
                  {visibleStepsStatus ?? "RunStep 用于稳定展示 Agent 执行过程。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {visibleSteps.map((step, index) => (
                  <div key={`${step.step_id}-${index}`} className="flex items-center justify-between gap-3 rounded-lg border bg-card px-3 py-2 text-xs">
                    <div className="min-w-0">
                      <code className="block truncate">{step.step_type}</code>
                      <span className="text-muted-foreground">{step.step_id}</span>
                    </div>
                    <Badge variant={step.status === "completed" ? "secondary" : step.status === "failed" ? "destructive" : "outline"}>
                      {step.status}
                    </Badge>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileClockIcon aria-hidden="true" />
                  Runtime Event
                </CardTitle>
                <CardDescription>
                  {evidence.eventsStatus ?? "事件用于端到端回放和审计。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {(evidence.events.length > 0 ? evidence.events.map((event) => event.event_type) : fallbackEvents).map((event, index) => (
                  <div key={`${event}-${index}`} className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-xs">
                    <RotateCcwIcon aria-hidden="true" className="text-muted-foreground" />
                    <code>{event}</code>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="diagnostics" className="flex flex-col gap-4 p-4">
            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <WrenchIcon aria-hidden="true" />
                  诊断状态
                </CardTitle>
                <CardDescription>
                  {diagnostics
                    ? `服务端状态：${diagnostics.status} · ${diagnostics.phase}`
                    : diagnosticsError
                      ? `诊断加载失败：${diagnosticsError}`
                      : "正在读取服务端诊断状态..."}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {diagnostics
                  ? Object.entries(diagnostics.checks).map(([key, value]) => (
                      <Badge key={key} variant={value === "ok" || value === "configured" ? "secondary" : "outline"}>
                        {key}: {value}
                      </Badge>
                    ))
                  : (
                      <>
                        <Badge variant="secondary">assistant-ui</Badge>
                        <Badge variant="secondary">shadcn</Badge>
                        <Badge variant="outline">OpenAI-compatible</Badge>
                        <Badge variant="outline">业务插件待接入</Badge>
                      </>
                    )}
              </CardContent>
            </Card>
          </TabsContent>
        </ScrollArea>
      </Tabs>
    </aside>
  );
}

export function WorkbenchShell({
  thread,
  renderThread,
  runtimeArtifact,
  activeThreadId,
  onSelectThread,
  onNewThread,
}: WorkbenchShellProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [localSelectedThreadId, setLocalSelectedThreadId] = useState<string | undefined>();
  const selectedThreadId = activeThreadId ?? localSelectedThreadId;
  const selectedThread = useThreadDetail(selectedThreadId);
  const historyHeader = undefined;
  const historyMessages = selectedThreadId
    ? <ThreadHistoryMessages detail={selectedThread.detail} status={selectedThread.status} />
    : undefined;
  const runEvidenceRefreshKey = runtimeArtifact
    ? [
        runtimeArtifact.status,
        runtimeArtifact.latestEvent,
        runtimeArtifact.events.at(-1),
        runtimeArtifact.events.length,
      ].filter(Boolean).join(":")
    : undefined;
  const runEvidence = useRunEvidence(runtimeArtifact?.runId, runEvidenceRefreshKey);
  return (
    <SidebarProvider>
      <WorkbenchSidebar
        onOpenSettings={() => setSettingsOpen(true)}
        selectedThreadId={selectedThreadId}
        onSelectThread={(threadId) => {
          setLocalSelectedThreadId(threadId);
          onSelectThread?.(threadId);
        }}
        onNewThread={() => {
          setLocalSelectedThreadId(undefined);
          onSelectThread?.(undefined);
          onNewThread?.();
        }}
      />
      <div className="flex h-svh min-w-0 flex-1 bg-background">
        <main aria-label="Agent 对话" className="relative min-w-0 flex-1">
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-4 top-3 z-10 hidden size-8 rounded-full lg:inline-flex"
            onClick={() => setInspectorOpen((open) => !open)}
            aria-label={inspectorOpen ? "收起运行证据" : "展开运行证据"}
          >
            {inspectorOpen ? (
              <ChevronRightIcon aria-hidden="true" className="size-4" />
            ) : (
              <ChevronLeftIcon aria-hidden="true" className="size-4" />
            )}
          </Button>
          {renderThread ? renderThread({ historyHeader, historyMessages }) : (
            <>
              {historyHeader}
              {historyMessages}
              {thread}
            </>
          )}
        </main>
        {inspectorOpen ? (
          <>
            <Separator orientation="vertical" />
            <RuntimeInspector
              runtimeArtifact={runtimeArtifact}
              evidence={runEvidence}
              onCollapse={() => setInspectorOpen(false)}
            />
          </>
        ) : null}
      </div>
      {settingsOpen ? <SettingsDialog onClose={() => setSettingsOpen(false)} /> : null}
    </SidebarProvider>
  );
}

function ThreadHistoryMessages({ detail, status }: { detail?: ThreadDetail; status?: string }) {
  return (
    <>
      {status ? (
        <div className="rounded-xl border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">{status}</div>
      ) : null}
      {detail?.messages.map((message) => (
        <article
          key={message.message_id}
          className={message.role === "user"
            ? "ml-auto max-w-[78%] rounded-2xl bg-muted px-4 py-3 text-sm"
            : "mr-auto max-w-[84%] px-2 py-1 text-sm leading-7"}
        >
          <p className="whitespace-pre-wrap">{message.content}</p>
        </article>
      ))}
      {detail && detail.messages.length === 0 ? (
        <div className="rounded-xl border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">该会话暂无消息。</div>
      ) : null}
    </>
  );
}

function SettingsDialog({ onClose }: { onClose: () => void }) {
  const [catalog, setCatalog] = useState<ModelCatalog | undefined>();
  const [error, setError] = useState<string | undefined>();
  const [testStatus, setTestStatus] = useState<string | undefined>();
  const model = catalog?.models[0];

  useEffect(() => {
    let cancelled = false;
    fetch("/api/models")
      .then((response) => {
        if (!response.ok) throw new Error(`http_${response.status}`);
        return response.json() as Promise<ModelCatalog>;
      })
      .then((body) => {
        if (!cancelled) setCatalog(body);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "unknown_error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function testConnection() {
    if (!model) return;
    const response = await fetch("/api/models/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: model.model_id }),
    });
    const body = await response.json() as { status?: string };
    setTestStatus(body.status ?? "unknown");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 p-4">
      <section
        role="dialog"
        aria-modal="true"
        aria-label="模型与设置"
        className="w-full max-w-xl rounded-xl border bg-background p-4 shadow-lg"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold">模型与设置</h2>
            <p className="mt-1 text-sm text-muted-foreground">模型调用使用 OpenAI-compatible 接口配置，由服务端安全持有密钥。</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>关闭</Button>
        </div>

        <div className="mt-4 rounded-lg border p-3">
          {error ? (
            <p className="text-sm text-destructive">模型配置读取失败：{error}</p>
          ) : model ? (
            <div className="grid gap-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium">{model.model_id}</div>
                  <div className="text-xs text-muted-foreground">{model.provider}</div>
                </div>
                <Badge variant={model.configured ? "secondary" : "outline"}>
                  {model.configured ? "模型已配置" : "模型未配置"}
                </Badge>
              </div>
              <div className="break-all rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
                {model.base_url}
              </div>
              <div className="flex flex-wrap gap-2">
                {model.capabilities.map((capability) => (
                  <Badge key={capability} variant="outline">{capability}</Badge>
                ))}
              </div>
              <div className="flex items-center gap-3">
                <Button size="sm" onClick={testConnection}>测试连接</Button>
                {testStatus ? <span className="text-sm text-muted-foreground">连接状态：{testStatus}</span> : null}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">正在读取模型配置...</p>
          )}
        </div>
      </section>
    </div>
  );
}
