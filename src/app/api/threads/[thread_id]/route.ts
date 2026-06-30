function workbenchServerUrl() {
  return (process.env.WORKBENCH_SERVER_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

async function threadTarget(req: Request, params: Promise<{ thread_id: string }>) {
  const { thread_id: threadId } = await params;
  const source = new URL(req.url);
  const target = new URL(`${workbenchServerUrl()}/api/threads/${encodeURIComponent(threadId)}`);
  for (const [key, value] of source.searchParams.entries()) {
    target.searchParams.set(key, value);
  }
  return target;
}

export async function GET(
  req: Request,
  { params }: { params: Promise<{ thread_id: string }> },
) {
  const target = await threadTarget(req, params);
  const response = await fetch(target.toString());
  const body = await response.json().catch(() => ({ detail: "invalid_thread_response" }));
  return Response.json(body, { status: response.ok ? 200 : response.status });
}

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ thread_id: string }> },
) {
  const target = await threadTarget(req, params);
  const response = await fetch(target.toString(), {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: await req.text(),
  });
  const body = await response.json().catch(() => ({ detail: "invalid_thread_update_response" }));
  return Response.json(body, { status: response.ok ? 200 : response.status });
}

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ thread_id: string }> },
) {
  const target = await threadTarget(req, params);
  const response = await fetch(target.toString(), { method: "DELETE" });
  const body = await response.json().catch(() => ({ detail: "invalid_thread_delete_response" }));
  return Response.json(body, { status: response.ok ? 200 : response.status });
}
