import { afterEach, describe, expect, it, vi } from "vitest";
import { DELETE, GET, PATCH } from "./route";

describe("thread detail proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("proxies a selected thread detail request to the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe(
        "http://python-server.test/api/threads/thread_recent?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo",
      );
      return Response.json({
        thread: {
          thread_id: "thread_recent",
          title: "历史会话",
          workspace_id: "workspace_default",
        },
        messages: [
          {
            message_id: "msg_user",
            role: "user",
            content: "历史问题",
            run_id: null,
          },
          {
            message_id: "msg_assistant",
            role: "assistant",
            content: "历史回答",
            run_id: "run_recent",
          },
        ],
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new Request("http://localhost/api/threads/thread_recent?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo"),
      { params: Promise.resolve({ thread_id: "thread_recent" }) },
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      thread: {
        thread_id: "thread_recent",
        title: "历史会话",
        workspace_id: "workspace_default",
      },
      messages: [
        {
          message_id: "msg_user",
          role: "user",
          content: "历史问题",
          run_id: null,
        },
        {
          message_id: "msg_assistant",
          role: "assistant",
          content: "历史回答",
          run_id: "run_recent",
        },
      ],
    });
  });

  it("proxies thread updates to the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(
        "http://python-server.test/api/threads/thread_recent?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo",
      );
      expect(init?.method).toBe("PATCH");
      expect(init?.body).toBe(JSON.stringify({ status: "archived" }));
      return Response.json({
        thread_id: "thread_recent",
        status: "archived",
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await PATCH(
      new Request("http://localhost/api/threads/thread_recent?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo", {
        method: "PATCH",
        body: JSON.stringify({ status: "archived" }),
      }),
      { params: Promise.resolve({ thread_id: "thread_recent" }) },
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      thread_id: "thread_recent",
      status: "archived",
    });
  });

  it("proxies thread deletion to the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(
        "http://python-server.test/api/threads/thread_recent?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo",
      );
      expect(init?.method).toBe("DELETE");
      return Response.json({ thread_id: "thread_recent", deleted: true });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await DELETE(
      new Request("http://localhost/api/threads/thread_recent?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo", {
        method: "DELETE",
      }),
      { params: Promise.resolve({ thread_id: "thread_recent" }) },
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ thread_id: "thread_recent", deleted: true });
  });
});
