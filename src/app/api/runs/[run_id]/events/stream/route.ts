function workbenchServerUrl() {
  return (process.env.WORKBENCH_SERVER_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function GET(_req: Request, { params }: { params: Promise<{ run_id: string }> }) {
  const { run_id: runId } = await params;
  const response = await fetch(`${workbenchServerUrl()}/api/runs/${runId}/events/stream`, {
    headers: { Accept: "text/event-stream" },
  });
  if (!response.ok || !response.body) {
    return Response.json({ detail: `runtime_event_stream_failed_${response.status}` }, { status: 502 });
  }
  return new Response(response.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
    },
  });
}
