"use client";

import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import {
  GripVerticalIcon,
  PanelRightIcon,
  PlusIcon,
  XIcon,
} from "lucide-react";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

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
  renderThread?: () => ReactNode;
  runtimeArtifact?: RuntimeArtifact;
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

export type RunStepRow = {
  step_id: string;
  step_type: string;
  status: string;
  payload?: Record<string, unknown>;
};

type BusinessPanelTab = {
  id: string;
  title: string;
};

function BusinessEmbedPanel({ open }: { open: boolean }) {
  const [tabs, setTabs] = useState<BusinessPanelTab[]>([
    { id: "panel-1", title: "面板 1" },
  ]);
  const [activeTabId, setActiveTabId] = useState("panel-1");

  function addTab() {
    const nextIndex = tabs.length + 1;
    const nextTab = {
      id: `panel-${Date.now()}`,
      title: `面板 ${nextIndex}`,
    };
    setTabs((currentTabs) => [...currentTabs, nextTab]);
    setActiveTabId(nextTab.id);
  }

  function closeTab(tabId: string) {
    if (tabs.length <= 1) return;

    const tabIndex = tabs.findIndex((tab) => tab.id === tabId);
    const nextTabs = tabs.filter((tab) => tab.id !== tabId);
    setTabs(nextTabs);

    if (activeTabId === tabId) {
      const fallbackTab =
        nextTabs[Math.min(Math.max(tabIndex - 1, 0), nextTabs.length - 1)];
      setActiveTabId(fallbackTab?.id ?? nextTabs[0]?.id ?? "panel-1");
    }
  }

  return (
    <aside
      aria-label="业务嵌入面板"
      aria-hidden={!open}
      className="flex size-full min-w-0 flex-col bg-background"
    >
      <div
        data-slot="business-panel-tabs"
        className="flex h-10 shrink-0 items-center gap-1 border-b px-2"
        role="tablist"
        aria-label="业务面板标签页"
      >
        {tabs.map((tab) => (
          <div
            key={tab.id}
            role="tab"
            tabIndex={0}
            aria-label={tab.title}
            aria-selected={activeTabId === tab.id}
            className={[
              "group/tab flex h-7 max-w-36 min-w-0 cursor-default items-center gap-1 rounded-md px-2 text-xs font-normal outline-none transition-colors",
              "hover:bg-accent hover:text-accent-foreground focus-visible:ring-ring/50 focus-visible:ring-[3px]",
              activeTabId === tab.id
                ? "bg-secondary text-secondary-foreground"
                : "text-foreground",
            ].join(" ")}
            onClick={() => setActiveTabId(tab.id)}
            onKeyDown={(event) => {
              if (event.key !== "Enter" && event.key !== " ") return;
              event.preventDefault();
              setActiveTabId(tab.id);
            }}
          >
            <span className="min-w-0 truncate">{tab.title}</span>
            <button
              type="button"
              aria-label={`关闭${tab.title}`}
              className="text-muted-foreground/70 hover:bg-background/70 hover:text-foreground focus-visible:ring-ring/50 ml-1 inline-flex size-4 shrink-0 items-center justify-center rounded-sm opacity-0 transition-opacity group-hover/tab:opacity-100 group-focus-within/tab:opacity-100"
              onClick={(event) => {
                event.stopPropagation();
                closeTab(tab.id);
              }}
              onKeyDown={(event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                event.stopPropagation();
                closeTab(tab.id);
              }}
            >
              <XIcon aria-hidden="true" className="size-3" />
            </button>
          </div>
        ))}
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="ml-auto size-7 rounded-md"
          onClick={addTab}
          aria-label="添加业务面板标签页"
        >
          <PlusIcon aria-hidden="true" className="size-4" />
        </Button>
      </div>
      <div
        className="min-h-0 flex-1 bg-muted/10"
        data-slot="business-panel-host"
        role="tabpanel"
        aria-label={tabs.find((tab) => tab.id === activeTabId)?.title ?? "业务面板"}
      />
    </aside>
  );
}

export function WorkbenchShell({
  thread,
  renderThread,
}: WorkbenchShellProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [businessPanelWidth, setBusinessPanelWidth] = useState(420);
  const [businessPanelResizing, setBusinessPanelResizing] = useState(false);
  const businessPanelResizeRef = useRef({ startX: 0, startWidth: 420 });

  function constrainBusinessPanelWidth(width: number) {
    if (typeof window === "undefined") return width;
    const maxWidth = Math.max(320, window.innerWidth * 0.45);
    return Math.min(Math.max(width, 280), maxWidth);
  }

  useEffect(() => {
    if (!businessPanelResizing) return;

    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    function handlePointerMove(event: globalThis.PointerEvent) {
      const deltaX = event.clientX - businessPanelResizeRef.current.startX;
      setBusinessPanelWidth(
        constrainBusinessPanelWidth(businessPanelResizeRef.current.startWidth - deltaX),
      );
    }

    function handlePointerUp() {
      setBusinessPanelResizing(false);
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp, { once: true });

    return () => {
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [businessPanelResizing]);

  function startBusinessPanelResize(event: PointerEvent<HTMLDivElement>) {
    if (!inspectorOpen) return;
    event.preventDefault();
    businessPanelResizeRef.current = {
      startX: event.clientX,
      startWidth: businessPanelWidth,
    };
    setBusinessPanelResizing(true);
  }

  return (
    <SidebarProvider>
      <ThreadListSidebar
        role="navigation"
        aria-label="工作台导航"
        collapsible="icon"
        variant="sidebar"
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <SidebarInset className="flex h-svh min-w-0 flex-1 bg-background">
        <div
          data-slot="assistant-business-sidebar"
          className="flex min-h-0 flex-1 overflow-hidden"
        >
          <main aria-label="Agent 对话" className="relative min-w-0 flex-1">
            <Button
              variant="ghost"
              size="icon-sm"
              className="absolute right-4 top-3 z-10 hidden rounded-[min(var(--radius-md),12px)] lg:inline-flex"
              onClick={() => setInspectorOpen((open) => !open)}
              aria-label={inspectorOpen ? "收起右侧面板" : "展开右侧面板"}
            >
              <PanelRightIcon aria-hidden="true" className="size-4 shrink-0" />
            </Button>
            {renderThread ? renderThread() : thread}
          </main>
          <div
            role="separator"
            aria-label="调整业务面板宽度"
            aria-orientation="vertical"
            aria-hidden={!inspectorOpen}
            data-slot="business-panel-resize-handle"
            className={cn(
              "relative hidden w-px shrink-0 cursor-col-resize items-center justify-center bg-border transition-opacity duration-200 ease-[cubic-bezier(0.25,1,0.5,1)] lg:flex motion-reduce:transition-none",
              inspectorOpen ? "opacity-100" : "pointer-events-none opacity-0",
            )}
            onPointerDown={startBusinessPanelResize}
          >
            <div className="bg-border z-10 flex h-4 w-3 items-center justify-center rounded-xs border">
              <GripVerticalIcon aria-hidden="true" className="size-2.5" />
            </div>
          </div>
          <div
            id="business-panel"
            className={cn(
              "hidden min-w-0 shrink-0 overflow-hidden border-l bg-background transition-[width] duration-200 ease-[cubic-bezier(0.25,1,0.5,1)] lg:block motion-reduce:transition-none",
              businessPanelResizing && "transition-none",
            )}
            style={{ width: inspectorOpen ? businessPanelWidth : 0 }}
          >
            <div
              className={
                inspectorOpen
                  ? "size-full opacity-100 transition-opacity duration-200"
                  : "pointer-events-none size-full opacity-0 transition-opacity duration-150"
              }
            >
              <BusinessEmbedPanel open={inspectorOpen} />
            </div>
          </div>
        </div>
      </SidebarInset>
      {settingsOpen ? <SettingsDialog onClose={() => setSettingsOpen(false)} /> : null}
    </SidebarProvider>
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
