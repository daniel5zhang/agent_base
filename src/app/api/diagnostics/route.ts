function workbenchServerUrl() {
  return (process.env.WORKBENCH_SERVER_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function GET() {
  const response = await fetch(`${workbenchServerUrl()}/api/diagnostics`);
  if (!response.ok) {
    return Response.json(
      {
        status: "error",
        phase: "phase_one",
        checks: {
          server: `http_${response.status}`,
        },
      },
      { status: 502 },
    );
  }
  return Response.json(await response.json());
}
