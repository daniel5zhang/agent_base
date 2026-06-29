import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

describe("run retry proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("proxies retry requests to the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("http://python-server.test/api/runs/run_test/retry");
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ user_id: "user_demo" }));
      return Response.json({
        run_id: "run_retry",
        retry_of_run_id: "run_test",
        status: "created",
        events: ["run.created", "retry_of_run"],
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(new Request("http://localhost/api/runs/run_test/retry", {
      method: "POST",
      body: JSON.stringify({ user_id: "user_demo" }),
    }), {
      params: Promise.resolve({ run_id: "run_test" }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      run_id: "run_retry",
      retry_of_run_id: "run_test",
      status: "created",
      events: ["run.created", "retry_of_run"],
    });
  });
});
