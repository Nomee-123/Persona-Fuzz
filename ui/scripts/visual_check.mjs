import fs from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer-core";

const base = process.env.PF_URL || "http://127.0.0.1:8000";
const chrome = process.env.PF_CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const outDir = path.resolve(process.env.PF_SCREENS || "../docs/screens");
fs.mkdirSync(outDir, { recursive: true });

const viewports = [
  { name: "1536x1024", width: 1536, height: 1024, routes: ["/", "/run", "/attacks", "/policy", "/report"] },
  { name: "1280x800", width: 1280, height: 800, routes: ["/"] },
  { name: "390x844", width: 390, height: 844, routes: ["/", "/attacks"] },
];

const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: "new",
  args: ["--disable-gpu", "--no-sandbox", "--hide-scrollbars"],
});

const results = [];
for (const vp of viewports) {
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));
  await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 1 });
  for (const route of vp.routes) {
    await page.goto(`${base}${route}`, { waitUntil: "networkidle0", timeout: 60000 });
    await page.waitForSelector(".stat-grid, .report-body, .panel", { timeout: 30000 });
    await new Promise((resolve) => setTimeout(resolve, 500));
    const audit = await page.evaluate(() => {
      const doc = document.documentElement;
      const body = document.body;
      const root = document.getElementById("root");
      const visible = (el) => {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      };
      const key = [".sidebar", ".topbar", ".content", ".stat-grid", ".panel"].map((sel) => {
        const el = document.querySelector(sel);
        if (!el || !visible(el)) return { sel, present: false };
        const r = el.getBoundingClientRect();
        return { sel, present: true, w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) };
      });
      return {
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        scrollWidth: Math.max(doc.scrollWidth, body.scrollWidth, root?.scrollWidth ?? 0),
        scrollHeight: Math.max(doc.scrollHeight, body.scrollHeight),
        horizontalOverflow: Math.max(doc.scrollWidth, body.scrollWidth, root?.scrollWidth ?? 0) > window.innerWidth + 1,
        key,
        sampleBadge: !!Array.from(document.querySelectorAll(".badge")).find((el) => el.textContent?.includes("Sample data")),
        title: document.querySelector("h1")?.textContent ?? "",
      };
    });
    const file = path.join(outDir, `${route === "/" ? "overview" : route.slice(1)}-${vp.name}.png`);
    await page.screenshot({ path: file, fullPage: false });
    results.push({ viewport: vp.name, route, file, consoleErrors, ...audit });
  }
  await page.close();
}
await browser.close();

const failures = results.filter((r) => r.horizontalOverflow || !r.sampleBadge || r.consoleErrors.length);
console.log(JSON.stringify({ ok: failures.length === 0, results, failures }, null, 2));
if (failures.length) process.exitCode = 1;
