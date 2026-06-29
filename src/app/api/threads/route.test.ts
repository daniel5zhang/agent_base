import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

describe("threads proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("proxies recent thread queries to the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe(
        "http://python-server.test/api/threads?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo",
      );
      return Response.json({
        threads: [
          {
            thread_id: "thread_recent",
            title: "帮我制定一阶段验收计划",
            workspace_id: "workspace_default",
            last_message: "已生成一阶段验收计划。",
            message_count: 2,
          },
        ],
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new Request(
      "http://localhost/api/threads?tenant_id=tenant_demo&workspace_id=workspace_default&user_id=user_demo",
    ));

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      threads: [
        {
          thread_id: "thread_recent",
          title: "帮我制定一阶段验收计划",
          workspace_id: "workspace_default",
          last_message: "已生成一阶段验收计划。",
          message_count: 2,
        },
      ],
    });
  });
});
