import { test, expect } from "@playwright/test";

test.skip(process.env.KNOWGRAPH_LIVE_API !== "1", "Requires the seeded FastAPI/FalkorDB stack");

test("same-origin proxy forwards health, encoded IDs, query strings and multipart validation", async ({ request }) => {
  const health = await request.get("/api/health");
  expect(health.ok()).toBeTruthy();
  expect(await health.json()).toMatchObject({ database: "ready" });
  const investigation = await request.get("/api/incidents/demo%3Ainc-payments/investigation?lookback_hours=24");
  expect(investigation.ok()).toBeTruthy();
  expect((await investigation.json()).incident.id).toBe("demo:inc-payments");
  const upload = await request.post("/api/ingest", { multipart: { bundle_file: { name: "invalid.json", mimeType: "application/json", buffer: Buffer.from("{invalid") } } });
  expect(upload.status()).toBe(422);
  expect((await upload.json()).detail).toBeTruthy();
  expect((await request.get("/api/not-allowed")).status()).toBe(404);
});
