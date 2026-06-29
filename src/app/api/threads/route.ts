function workbenchServerUrl() {
  return (process.env.WORKBENCH_SERVER_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function GET(req: Request) {
  const source = new URL(req.url);
  const target = new URL(`${workbenchServerUrl()}/api/threads`);
  for (const [key, value] of source.searchParams.entries()) {
    target.searchParams.set(key, value);
  }
  const response = await fetch(target.toString());
  return Response.json(await response.json(), { status: response.ok ? 200 : 502 });
}
