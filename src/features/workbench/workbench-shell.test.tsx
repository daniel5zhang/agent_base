import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import {
  AssistantChatTransport,
  useChatRuntime,
} from "@assistant-ui/react-ai-sdk";
import { WorkbenchShell } from "./workbench-shell";

function TestWorkbenchShell({ thread = <div data-testid="assistant-thread-slot">Thread</div> }: { thread?: React.ReactNode }) {
  const runtime = useChatRuntime({
    transport: new AssistantChatTransport({ api: "/api/chat" }),
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <WorkbenchShell thread={thread} />
    </AssistantRuntimeProvider>
  );
}

describe("assistant-ui-first workbench shell", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the enterprise workbench around an assistant-ui thread slot", () => {
    render(<TestWorkbenchShell />);

    expect(screen.getByRole("navigation", { name: "工作台导航" })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "Agent 对话" })).toBeInTheDocument();
    expect(screen.getByTestId("assistant-thread-slot")).toBeInTheDocument();
    expect(screen.queryByText("默认工作空间")).not.toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "业务嵌入面板" })).not.toBeInTheDocument();
    expect(document.querySelector('[data-slot="sidebar"]')).toBeInTheDocument();
  });

  it("opens a tabbed right-side business embed panel", () => {
    render(<TestWorkbenchShell />);

    const panelContainer = document.querySelector("#business-panel");
    expect(panelContainer).toHaveClass("transition-[width]");
    expect(panelContainer).toHaveStyle({ width: "0px" });

    fireEvent.click(screen.getByRole("button", { name: "展开右侧面板" }));

    const panel = screen.getByRole("complementary", { name: "业务嵌入面板" });
    expect(panel).toBeInTheDocument();
    expect(panelContainer).toHaveStyle({ width: "420px" });
    expect(within(panel).queryByText("业务面板")).not.toBeInTheDocument();
    expect(within(panel).getByRole("tablist", { name: "业务面板标签页" })).toBeInTheDocument();
    expect(within(panel).getByRole("tab", { name: "面板 1" })).toHaveAttribute("aria-selected", "true");
    expect(panel.querySelector('[data-slot="business-panel-host"]')).toBeInTheDocument();
    expect(within(panel).queryByText("运行证据")).not.toBeInTheDocument();
    expect(within(panel).queryByText("Artifact")).not.toBeInTheDocument();
    expect(within(panel).queryByText("审计编号")).not.toBeInTheDocument();
    expect(within(panel).queryByText("运行边界")).not.toBeInTheDocument();

    fireEvent.click(within(panel).getByRole("button", { name: "添加业务面板标签页" }));
    expect(within(panel).getByRole("tab", { name: "面板 2" })).toHaveAttribute("aria-selected", "true");

    fireEvent.click(within(panel).getByRole("button", { name: "关闭面板 2" }));
    expect(within(panel).queryByRole("tab", { name: "面板 2" })).not.toBeInTheDocument();
    expect(within(panel).getByRole("tab", { name: "面板 1" })).toHaveAttribute("aria-selected", "true");

    fireEvent.click(within(panel).getByRole("button", { name: "关闭面板 1" }));
    expect(within(panel).getByRole("tab", { name: "面板 1" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "收起右侧面板" }));
    expect(screen.queryByRole("complementary", { name: "业务嵌入面板" })).not.toBeInTheDocument();
    expect(panelContainer).toHaveStyle({ width: "0px" });
  });

  it("does not fetch runtime evidence or diagnostics when opening the empty right panel", () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({}));

    render(<TestWorkbenchShell thread={<div />} />);
    fireEvent.click(screen.getByRole("button", { name: "展开右侧面板" }));

    expect(fetchMock).not.toHaveBeenCalledWith("/api/diagnostics");
    expect(fetchMock.mock.calls.some(([input]) => String(input).startsWith("/api/runs/"))).toBe(false);
  });

  it("uses assistant-ui thread list primitives for new-thread navigation", async () => {
    render(<TestWorkbenchShell />);
    const main = screen.getByRole("main", { name: "Agent 对话" });

    expect(document.querySelector('[data-slot="aui_thread-list-root"]')).toBeInTheDocument();
    expect(document.querySelector('[data-slot="aui_thread-list-new"]')).toBeInTheDocument();
    expect(within(main).getByTestId("assistant-thread-slot")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "新建任务" }));
    expect(within(main).getByTestId("assistant-thread-slot")).toBeInTheDocument();
  });

  it("expands the collapsed sidebar when clicking the brand logo", () => {
    render(<TestWorkbenchShell />);

    const sidebar = document.querySelector('[data-slot="sidebar"]');
    expect(sidebar).toHaveAttribute("data-state", "expanded");

    fireEvent.click(screen.getByRole("button", { name: "折叠左侧会话列表" }));
    expect(sidebar).toHaveAttribute("data-state", "collapsed");

    fireEvent.click(screen.getByRole("button", { name: "展开左侧会话列表" }));
    expect(sidebar).toHaveAttribute("data-state", "expanded");
  });

  it("opens settings and loads configured models", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
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

    render(<TestWorkbenchShell thread={<div />} />);
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
});
