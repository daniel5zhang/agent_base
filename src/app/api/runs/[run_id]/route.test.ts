import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

describe("run detail proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("proxies run steps from the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("http://python-server.test/api/runs/run_failed");
      return Response.json({
        run_id: "run_failed",
        status: "failed",
        question: "触发失败工具测试",
        steps: [
          {
            step_id: "step_tool_failed",
            step_type: "tool:diagnostic.check",
            status: "failed",
            payload: { tool_id: "diagnostic.check" },
          },
        ],
        events: [
          {
            event_id: "evt_failed",
            event_type: "tool.failed",
            payload_digest: "digest_failed",
          },
        ],
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new Request("http://localhost/api/runs/run_failed"), {
      params: Promise.resolve({ run_id: "run_failed" }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      run_id: "run_failed",
      status: "failed",
      steps: [
        {
          step_id: "step_tool_failed",
          step_type: "tool:diagnostic.check",
          status: "failed",
        },
      ],
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
