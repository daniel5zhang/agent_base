import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

describe("run events proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("proxies ordered runtime events from the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("http://python-server.test/api/runs/run_test/events");
      return Response.json({
        events: [
          {
            event_id: "evt_1",
            event_type: "run.created",
            payload_digest: "digest_1",
            occurred_at: "2026-06-26T00:00:00+00:00",
          },
        ],
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new Request("http://localhost/api/runs/run_test/events"), {
      params: Promise.resolve({ run_id: "run_test" }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      events: [
        {
          event_id: "evt_1",
          event_type: "run.created",
          payload_digest: "digest_1",
          occurred_at: "2026-06-26T00:00:00+00:00",
        },
      ],
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
