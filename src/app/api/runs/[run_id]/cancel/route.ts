function workbenchServerUrl() {
  return (process.env.WORKBENCH_SERVER_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function POST(req: Request, { params }: { params: Promise<{ run_id: string }> }) {
  const { run_id: runId } = await params;
  const response = await fetch(`${workbenchServerUrl()}/api/runs/${runId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
  return Response.json(await response.json(), { status: response.ok ? 200 : 502 });
}
