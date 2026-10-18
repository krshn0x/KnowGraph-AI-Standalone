import { test, expect, type Page } from "@playwright/test";
import fixtures from "./fixtures/workspace.json";

// Fictional Northstar Labs responses captured from the seeded FastAPI service.
// Browser interception is test-only; the application always calls the real API.
async function workspace(page: Page) {
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    const path = decodeURIComponent(url.pathname.slice(4));
    let data: unknown;
    if (path === "/health") data = { ...fixtures.health, ai_configured: false };
    else if (path === "/entities") data = url.searchParams.get("kind") === "Incident" ? fixtures.incidents : url.searchParams.get("kind") === "Service" ? fixtures.services : fixtures.search;
    else if (path.startsWith("/incidents/")) data = path.includes("inc-payments") ? fixtures.payments : path.includes("inc-queue") ? fixtures.queue : fixtures.checkout;
    else if (path === "/experts") data = url.searchParams.get("q") === "unfindable" ? { experts: [], evidence: fixtures.experts.evidence } : fixtures.experts;
    else if (path === "/documents") data = url.searchParams.get("q") === "unfindable" ? { documents: [], evidence: fixtures.documents.evidence } : fixtures.documents;
    else if (path === "/graph/neighborhood") data = fixtures.neighborhood;
    else return route.fulfill({ status: 404, json: { detail: "Unexpected test request" } });
    await route.fulfill({ json: data });
  });
}

test.beforeEach(async ({ page }) => { await workspace(page); });

test("overview uses real counts, inspects sources, highlights and exports actual graph paths", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("FalkorDB connected", { exact: true })).toBeVisible();
  await expect(page.locator(".stat-value").first()).toHaveText(String(fixtures.health.nodes));
  await expect(page.locator(".react-flow__node").first()).toBeVisible();
  await page.getByLabel("Highlight evidence path").selectOption({ index: 1 });
  await expect(page.locator(".record-node.highlighted").first()).toBeVisible();
  await page.locator(".react-flow__node").first().click();
  await expect(page.getByRole("dialog", { name: "Source record" })).toContainText("SOURCE REFERENCE");
  await page.keyboard.press("Escape");
  const downloaded = page.waitForEvent("download");
  await page.getByLabel("Export evidence").click();
  expect((await downloaded).suggestedFilename()).toBe("knowgraph-evidence.json");
  await page.screenshot({ path: "test-results/overview-desktop.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("investigates dependency failures and changes the deployment lookback", async ({ page }) => {
  await page.goto("/investigations");
  await page.getByLabel("Select incident").selectOption("demo:inc-payments");
  await expect(page.locator(".incident-title h2")).toHaveText(fixtures.payments.incident.title);
  await expect(page.locator(".service-chips")).toContainText("ledger");
  const request = page.waitForRequest(r => r.url().includes("lookback_hours=6"));
  await page.getByLabel("Deployment lookback").selectOption("6");
  await request;
  await page.getByRole("button", { name: "View source", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("demo:inc-payments");
  await page.keyboard.press("Escape");
  await page.getByLabel("Select incident").selectOption("demo:inc-queue");
  await expect(page.locator(".incident-title h2")).toHaveText(fixtures.queue.incident.title);
});

test("expert and document search expose supporting sources and empty states", async ({ page }) => {
  await page.goto("/experts");
  await expect(page.locator(".expert-name").first()).toContainText(fixtures.experts.experts[0].person.title);
  await page.locator(".expert-reason:not([disabled])").first().click();
  await expect(page.getByRole("dialog", { name: "Source record" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByLabel("Service, incident ID, or topic").fill("unfindable");
  await page.getByRole("button", { name: "Find experts", exact: true }).click();
  await expect(page.getByText("No supported expert matches")).toBeVisible();
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await page.getByRole("button", { name: "Runbooks", exact: true }).click();
  await expect(page.locator(".document-card").first()).toContainText(/runbook/i);
  await page.locator(".document-card").first().click();
  await expect(page.getByRole("dialog")).toContainText("SOURCE REFERENCE");
  await page.keyboard.press("Escape");
  await page.getByLabel("Search documents and tickets").fill("unfindable");
  await page.getByRole("button", { name: "Search knowledge", exact: true }).click();
  await expect(page.getByText("No matching knowledge")).toBeVisible();
});

test("graph exploration sends the selected source and depth; global search opens a source", async ({ page }) => {
  await page.goto("/graph");
  await page.getByRole("button", { name: "Explore a source", exact: true }).click();
  await page.getByLabel("Starting source ID").fill("demo:checkout");
  await page.getByLabel("Relationship depth").selectOption("3");
  const request = page.waitForRequest(r => r.url().includes("node_id=demo%3Acheckout&hops=3"));
  await page.getByRole("button", { name: "Explore graph", exact: true }).click();
  await request;
  await expect(page.locator(".react-flow__node")).toHaveCount(fixtures.neighborhood.nodes.length);
  await page.keyboard.press("Control+k");
  await page.getByRole("textbox", { name: "Search company knowledge", exact: true }).fill("checkout");
  await page.getByRole("dialog").locator(".source-row").first().click();
  await expect(page.getByRole("dialog", { name: "Source record" })).toBeVisible();
});

test("JSON and CSV uploads send multipart files, show rejection counts, and refresh after success", async ({ page }) => {
  let uploads = 0;
  await page.route("**/api/ingest", async route => {
    uploads++;
    expect(route.request().headers()["content-type"]).toContain("multipart/form-data");
    expect(route.request().postData()).toContain(uploads === 1 ? "bundle_file" : "nodes_file");
    await route.fulfill(uploads === 1 ? { status: 422, json: { created: 0, updated: 0, unchanged: 0, rejected: 1, errors: ["Unknown relationship endpoint"] } } : { json: { created: 1, updated: 0, unchanged: 0, rejected: 0, errors: [] } });
  });
  await page.goto("/sources");
  await page.getByRole("button", { name: "Validate & import" }).click();
  await expect(page.locator(".error-notice")).toContainText("Choose a file");
  await page.getByLabel("JSON bundle", { exact: true }).setInputFiles({ name: "invalid.json", mimeType: "application/json", buffer: Buffer.from('{"nodes":[],"edges":[]}') });
  await page.getByRole("button", { name: "Validate & import" }).click();
  await expect(page.locator(".error-notice")).toContainText("Unknown relationship endpoint");
  await expect(page.locator(".import-result")).toContainText("Import rejected");
  await page.getByRole("button", { name: "CSV files", exact: true }).click();
  await page.getByLabel("Nodes CSV", { exact: true }).setInputFiles({ name: "nodes.csv", mimeType: "text/csv", buffer: Buffer.from("id,kind,title,source_ref\ncompany:test,Service,Test,demo:test") });
  await page.getByRole("button", { name: "Validate & import" }).click();
  await expect(page.locator(".import-result")).toContainText("Knowledge is up to date");
  await expect(page.locator(".toast")).toContainText("Knowledge updated");
  expect(uploads).toBe(2);
});

test("answers preserve history across navigation and let users inspect citations", async ({ page }) => {
  let questions = 0;
  const evidence = fixtures.checkout.evidence;
  await page.route("**/api/ask", async route => {
    questions++;
    const body = route.request().postDataJSON();
    expect(body.history).toHaveLength(questions === 1 ? 0 : 2);
    await route.fulfill({ json: {
      summary: "A deployment preceded the recorded checkout incident.",
      claims: [{ text: "The graph connects this incident to the affected service.", certainty: "observed", evidence_ids: [evidence.paths[0].id] }],
      insufficient_evidence: false, evidence, retrieved_evidence: evidence, sources: [fixtures.checkout.incident],
      experts: fixtures.experts.experts.slice(0, 1), warnings: [], tool_calls: ["investigate_incident"], status: "ok",
    } });
  });
  await page.goto("/ask");
  await expect(page.getByText("AI answers aren’t configured")).toBeVisible();
  await page.getByRole("textbox", { name: "Ask KnowGraph", exact: true }).fill("Investigate checkout");
  await page.getByLabel("Send question").click();
  await expect(page.locator(".answer-summary")).toContainText("A deployment preceded");
  await page.locator(".citation-chip").click();
  await expect(page.getByRole("dialog", { name: "Supporting graph evidence" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await page.getByRole("link", { name: "Ask KnowGraph AI", exact: true }).click();
  await expect(page.locator(".answer-summary")).toContainText("A deployment preceded");
  await page.getByRole("textbox", { name: "Ask KnowGraph", exact: true }).fill("Who can help?");
  await page.getByLabel("Send question").click();
  await expect(page.locator(".answer-summary")).toHaveCount(2);
  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.locator(".answer-summary")).toHaveCount(0);
});

test("outages retain the question and present retryable failures", async ({ page }) => {
  await page.route("**/api/health", route => route.fulfill({ status: 503, json: { detail: "Knowledge service unavailable" } }));
  await page.route("**/api/ask", route => route.fulfill({ status: 503, json: { detail: "AI provider unavailable" } }));
  await page.goto("/ask");
  await expect(page.locator(".error-notice").first()).toContainText("Knowledge service unavailable");
  await page.getByRole("textbox", { name: "Ask KnowGraph", exact: true }).fill("Investigate checkout");
  await page.getByLabel("Send question").click();
  await expect(page.getByRole("textbox", { name: "Ask KnowGraph", exact: true })).toHaveValue("Investigate checkout");
  await expect(page.locator(".error-notice").last()).toContainText("AI provider unavailable");
});

test("mobile navigation and import controls fit the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator(".stat-value").first()).toHaveText(String(fixtures.health.nodes));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/overview-mobile.png", fullPage: true });
  await page.getByLabel("Open navigation").click();
  await page.getByRole("link", { name: "Data sources", exact: true }).click();
  await expect(page.getByRole("button", { name: "Validate & import" })).toBeVisible();
  await expect(page.locator(".sidebar")).toHaveCSS("transform", "matrix(1, 0, 0, 1, -220, 0)");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/sources-mobile.png", fullPage: true });
});

test("Token Harbour settings prefill defaults, preserve edits, and save a write-only key", async ({ page }) => {
  let saved = false;
  const settings = () => ({ provider: saved ? "agentrouter" : "openai", configured: saved, storage: saved ? "session" : "environment", providers: {
    openai: { model: "gpt-6.1-sol", base_url: "https://api.openai.com/v1", has_api_key: false },
    agentrouter: { model: saved ? "my-deepseek-v4" : "", base_url: saved ? "https://router.example.test/v1" : "", has_api_key: saved },
    gemini: { model: "gemini-3.8-flash", base_url: "https://generativelanguage.googleapis.com/v1beta", has_api_key: false },
    ollama: { model: "qwen3:4b", base_url: "http://host.docker.internal:11434/v1", has_api_key: false },
  } });
  await page.route("**/api/settings/ai", async route => {
    if (route.request().method() === "POST") {
      expect(route.request().postDataJSON()).toEqual({ provider: "agentrouter", model: "my-deepseek-v4", base_url: "https://router.example.test/v1", api_key: "fake-router-key-for-ui-test" });
      saved = true;
    }
    await route.fulfill({ json: settings() });
  });
  await page.route("**/api/health", route => route.fulfill({ json: { ...fixtures.health, provider: saved ? "agentrouter" : "openai", model: saved ? "my-deepseek-v4" : "gpt-6.1-sol", ai_configured: saved } }));
  await page.goto("/ask");
  await page.getByRole("button", { name: "AI settings", exact: true }).click();
  await page.getByLabel("AI provider", { exact: true }).selectOption({ label: "Token Harbour" });
  await expect(page.getByLabel("Token Harbour API base URL")).toHaveValue("https://tokenharbor.ai/v1");
  await expect(page.getByLabel("AI model ID")).toHaveValue("deepseek-v4.1-flash:free");
  await page.getByLabel("Token Harbour API base URL").fill("https://router.example.test/v1");
  await page.getByLabel("AI model ID").fill("my-deepseek-v4");
  await page.getByLabel("Provider API key").fill("fake-router-key-for-ui-test");
  await expect(page.getByLabel("Provider API key")).toHaveAttribute("type", "password");
  await page.getByRole("button", { name: "Save AI settings" }).click();
  await expect(page.locator(".model-tag")).toContainText("my-deepseek-v4");
  await expect(page.getByText("AI answers aren’t configured")).toHaveCount(0);
  await page.getByRole("button", { name: "System status", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Token Harbour");
  await page.getByRole("button", { name: "Configure AI provider", exact: true }).click();
  await expect(page.getByLabel("Token Harbour API base URL")).toHaveValue("https://router.example.test/v1");
  await expect(page.getByLabel("AI model ID")).toHaveValue("my-deepseek-v4");
  await expect(page.getByLabel("Provider API key")).toHaveValue("");
  await expect(page.getByText("Saved on backend")).toBeVisible();
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain("fake-router-key-for-ui-test");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "test-results/ai-settings-mobile.png" });
});

test("Gemini is absent from settings and legacy configurations can switch to Token Harbour", async ({ page }) => {
  let saved = false;
  const endpoint = "https://tokenharbor.ai/v1";
  const model = "deepseek-v4.1-flash:free";
  const payload = { provider: "agentrouter", model, base_url: endpoint, api_key: "fake-token-harbour-ui-key" };
  await page.route("**/api/settings/ai", async route => {
    if (route.request().method() === "POST") {
      expect(route.request().postDataJSON()).toEqual(payload);
      saved = true;
    }
    await route.fulfill({ json: { provider: saved ? "agentrouter" : "gemini", configured: true, storage: saved ? "session" : "environment", providers: {
      openai: { model: "gpt-6.1-sol", base_url: "https://api.openai.com/v1", has_api_key: false },
      agentrouter: { model: saved ? model : "", base_url: saved ? endpoint : "", has_api_key: saved },
      gemini: { model: "gemini-3.8-flash", base_url: "https://generativelanguage.googleapis.com/v1beta", has_api_key: true },
      ollama: { model: "qwen3:4b", base_url: "http://host.docker.internal:11434/v1", has_api_key: false },
    } } });
  });
  await page.route("**/api/health", route => route.fulfill({ json: { ...fixtures.health, provider: saved ? "agentrouter" : "gemini", model: saved ? model : "gemini-3.8-flash", ai_configured: true } }));
  await page.goto("/ask");
  await page.getByRole("button", { name: "AI settings", exact: true }).click();
  await expect(page.getByLabel("AI provider", { exact: true })).toHaveValue("agentrouter");
  await expect(page.getByLabel("AI provider").locator("option")).toHaveText(["OpenAI", "Token Harbour", "Local Ollama"]);
  await expect(page.getByLabel("AI model ID")).toHaveValue(model);
  await expect(page.getByLabel("Token Harbour API base URL")).toHaveValue(endpoint);
  await expect(page.getByLabel("Provider API key")).toHaveValue("");
  await expect(page.getByLabel("Provider API key")).toHaveAttribute("required", "");
  await expect(page.getByText("Saved on backend")).toHaveCount(0);
  await expect(page.getByRole("dialog")).not.toContainText("Gemini");
  await page.route("**/api/settings/ai/test", async route => {
    expect(route.request().postDataJSON()).toEqual(payload);
    expect(saved).toBe(false);
    await route.fulfill({ json: { ok: true, provider: "agentrouter", model, message: "Model access, graph tool calling, and a cited answer were verified. These settings have not been saved." } });
  });
  await page.getByLabel("Provider API key").fill(payload.api_key);
  await page.getByRole("button", { name: "Test connection", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("have not been saved");
  await page.getByRole("button", { name: "Save AI settings" }).click();
  await expect(page.locator(".model-tag")).toContainText(model);
  await page.getByRole("button", { name: "System status", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Token Harbour");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "AI settings", exact: true }).click();
  await expect(page.getByLabel("Provider API key")).toHaveValue("");
  await expect(page.getByText("Saved on backend")).toBeVisible();
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(payload.api_key);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "test-results/token-harbour-settings-mobile.png" });
});

test("local Ollama can be selected and saved without any API key", async ({ page }) => {
  let saved = false;
  const baseURL = "http://host.docker.internal:11434/v1";
  await page.route("**/api/settings/ai", async route => {
    if (route.request().method() === "POST") {
      expect(route.request().postDataJSON()).toEqual({ provider: "ollama", model: "qwen3:4b", base_url: baseURL, deadline_seconds: 450 });
      saved = true;
    }
    await route.fulfill({ json: { provider: saved ? "ollama" : "openai", configured: saved, storage: saved ? "session" : "environment", providers: {
      openai: { model: "gpt-6.1-sol", base_url: "https://api.openai.com/v1", has_api_key: false },
      agentrouter: { model: "", base_url: "", has_api_key: false },
      gemini: { model: "gemini-3.8-flash", base_url: "https://generativelanguage.googleapis.com/v1beta", has_api_key: false },
      ollama: { model: "qwen3:4b", base_url: baseURL, has_api_key: false, deadline_seconds: saved ? 450 : 300 },
    } } });
  });
  await page.route("**/api/health", route => route.fulfill({ json: { ...fixtures.health, provider: saved ? "ollama" : "openai", model: saved ? "qwen3:4b" : "gpt-6.1-sol", ai_configured: saved } }));
  await page.goto("/ask");
  await page.getByRole("button", { name: "AI settings", exact: true }).click();
  await page.getByLabel("AI provider", { exact: true }).selectOption("agentrouter");
  await page.getByLabel("Provider API key").fill("cloud-key-must-not-go-to-ollama");
  await page.getByLabel("AI provider", { exact: true }).selectOption("ollama");
  await expect(page.getByLabel("Provider API key")).toHaveCount(0);
  await expect(page.getByRole("dialog")).toContainText("No API key is needed");
  await expect(page.getByLabel("AI model ID")).toHaveValue("qwen3:4b");
  await expect(page.getByLabel("Ollama API base URL")).toHaveValue(baseURL);
  await expect(page.getByLabel("Ollama investigation deadline")).toHaveValue("300");
  await page.getByLabel("Ollama investigation deadline").fill("450");
  await page.getByRole("button", { name: "Save AI settings" }).click();
  await expect(page.locator(".model-tag")).toContainText("qwen3:4b");
  await page.getByRole("button", { name: "System status", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Local Ollama");
  await expect(page.getByRole("dialog")).toContainText("Provider configured");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "AI settings", exact: true }).click();
  await expect(page.getByLabel("Provider API key")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel("Ollama investigation deadline")).toHaveValue("450");
  await page.getByRole("button", { name: "Save AI settings" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: "test-results/ollama-settings-mobile.png" });
});
