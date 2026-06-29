import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

describe("run cancel proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("proxies cancel requests to the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("http://python-server.test/api/runs/run_test/cancel");
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ user_id: "user_demo", reason: "用户取消" }));
      return Response.json({ run_id: "run_test", status: "cancelled", events: ["run.cancelled"] });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(new Request("http://localhost/api/runs/run_test/cancel", {
      method: "POST",
      body: JSON.stringify({ user_id: "user_demo", reason: "用户取消" }),
    }), {
      params: Promise.resolve({ run_id: "run_test" }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ run_id: "run_test", status: "cancelled", events: ["run.cancelled"] });
  });
});
