import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

describe("diagnostics proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("proxies phase-one diagnostics from the Python server", async () => {
    vi.stubEnv("WORKBENCH_SERVER_URL", "http://python-server.test");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("http://python-server.test/api/diagnostics");
      return Response.json({
        status: "ok",
        phase: "phase_one",
        checks: {
          sqlite: "ok",
          model: "configured",
          business_plugins: "disabled_until_phase_two",
        },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      status: "ok",
      phase: "phase_one",
      checks: {
        sqlite: "ok",
        model: "configured",
        business_plugins: "disabled_until_phase_two",
      },
    });
  });
});
