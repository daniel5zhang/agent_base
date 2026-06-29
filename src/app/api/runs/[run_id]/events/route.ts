function workbenchServerUrl() {
  return (process.env.WORKBENCH_SERVER_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function GET(_req: Request, { params }: { params: Promise<{ run_id: string }> }) {
  const { run_id: runId } = await params;
  const response = await fetch(`${workbenchServerUrl()}/api/runs/${runId}/events`);
  return Response.json(await response.json(), { status: response.ok ? 200 : 502 });
}
