/* eslint-disable @typescript-eslint/no-unused-expressions */
async (page) => {
  await page.unroute("**/api/chat").catch(() => undefined);

  const appUrl = page.url() || "http://127.0.0.1:3011";
  await page.goto(appUrl);
  await page.waitForLoadState("domcontentloaded");

  const textbox = page.getByRole("textbox", { name: "发送消息" });
  await textbox.fill("服务端不可用测试，请保留可见错误");
  await textbox.press("Enter");

  await page.getByText("服务端不可用或运行失败", { exact: false }).waitFor({ timeout: 15000 });

  const bodyText = await page.locator("body").innerText();
  if (!bodyText.includes("服务端不可用或运行失败")) {
    throw new Error("missing visible server unavailable error");
  }
  if (bodyText.includes("run.completed")) {
    throw new Error("server unavailable path must not show run.completed");
  }
  if (!bodyText.includes("服务端不可用测试，请保留可见错误")) {
    throw new Error("user message should remain visible after server failure");
  }

  await page.screenshot({
    path: "/Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/output/playwright/phase1-server-unavailable.png",
    fullPage: true,
  });
  return bodyText;
}
