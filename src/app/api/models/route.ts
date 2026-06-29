function workbenchServerUrl() {
  return (process.env.WORKBENCH_SERVER_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function GET() {
  const response = await fetch(`${workbenchServerUrl()}/api/models`);
  return Response.json(await response.json(), { status: response.ok ? 200 : 502 });
}
