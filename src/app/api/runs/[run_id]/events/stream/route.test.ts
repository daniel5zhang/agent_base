import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

describe("run event stream proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("proxies runtime event SSE from the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("http://python-server.test/api/runs/run_test/events/stream");
      return new Response("event: runtime_event\ndata: {\"event_type\":\"run.created\"}\n\n", {
        headers: { "Content-Type": "text/event-stream" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new Request("http://localhost/api/runs/run_test/events/stream"), {
      params: Promise.resolve({ run_id: "run_test" }),
    });

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    expect(await response.text()).toContain("run.created");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
