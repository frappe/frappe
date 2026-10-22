// Fails when a cold desk v2 load or a save sends more API calls than its baseline.
import fs from "fs";
import path from "path";
import { test, expect, ADMIN_PASSWORD, TEST_USER } from "../support";
import { Api } from "../support/api";
import { site_url } from "../support/config";

const BUDGETS = "frontend/speed-budgets.json";
const QUIET_MS = 1500;
const MAX_WAITS = 20;

const budgets = JSON.parse(fs.readFileSync(path.join(__dirname, "../..", BUDGETS), "utf8"));

test.describe("Desk v2 API calls", () => {
	let request;
	let todo;

	// The ToDo belongs to the test user, who loads the pages.
	test.beforeAll(async ({ playwright }, workerInfo) => {
		request = await playwright.request.newContext({
			baseURL: site_url(workerInfo.parallelIndex),
		});
		const res = await request.post("/api/method/login", {
			data: { usr: TEST_USER, pwd: ADMIN_PASSWORD },
		});
		expect(res.status(), `login as ${TEST_USER}: ${await res.text()}`).toBe(200);
		const r = await new Api(request).call("frappe.tests.ui_test_helpers.create_todo", {
			description: "Count the desk v2 API calls",
		});
		todo = r.message.name;
	});

	test.afterAll(async () => {
		if (todo) await new Api(request).remove_doc("ToDo", todo, true);
		await request?.dispose();
	});

	test("loads home cold", async ({ page }) => {
		expect_baseline("home", await cold_visit(page, "/apps/desk"));
	});

	test("loads the list cold", async ({ page }) => {
		expect_baseline("list", await cold_visit(page, "/apps/desk/todo"));
	});

	test("loads a record cold", async ({ page }) => {
		expect_baseline("record", await cold_visit(page, `/apps/desk/todo/${todo}`));
	});

	test("saves a record", async ({ page }) => {
		await cold_visit(page, `/apps/desk/todo/${todo}`);
		await page.locator('[data-fieldname="description"]').click();
		await page.keyboard.type(" again");
		const calls = await count_calls(page, () =>
			page.getByRole("button", { name: "Save", exact: true }).click()
		);
		expect_baseline("save", calls);

		const res = await page.request.get(`/api/v2/document/ToDo/${todo}`);
		expect(res.status()).toBe(200);
		expect((await res.json()).data.description).toContain(" again");
	});
});

function expect_baseline(name, calls) {
	const baseline = budgets[name].baseline.calls;
	const message =
		`${name} sent ${calls.length} API calls, baseline ${baseline}. ` +
		`Remove the calls, or raise the baseline in ${BUDGETS} to ${calls.length}.\n` +
		calls.join("\n");
	expect(calls.length, message).toBeLessThanOrEqual(baseline);
}

// Each test gets a new browser context, so local and session storage start empty.
async function cold_visit(page, url) {
	// With the cache on, a GET repeated in one load reaches the network or not depending on timing.
	const cdp = await page.context().newCDPSession(page);
	await cdp.send("Network.enable");
	await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
	return count_calls(page, () => page.goto(url));
}

async function count_calls(page, action) {
	const calls = [];
	const pending = new Set();
	const on_request = (req) => {
		const url = new URL(req.url());
		if (!url.pathname.startsWith("/api/")) return;
		calls.push(`${req.method()} ${url.pathname}${url.search}`);
		pending.add(req);
	};
	const on_done = (req) => pending.delete(req);

	page.on("request", on_request);
	page.on("requestfinished", on_done);
	page.on("requestfailed", on_done);
	try {
		await action();
		await wait_for_quiet(page, calls, pending);
	} finally {
		page.off("request", on_request);
		page.off("requestfinished", on_done);
		page.off("requestfailed", on_done);
	}
	return calls;
}

async function wait_for_quiet(page, calls, pending) {
	let seen = -1;
	for (let waits = 0; ; waits++) {
		await page.waitForTimeout(QUIET_MS);
		if (!pending.size && calls.length === seen) return;
		if (waits === MAX_WAITS) {
			throw new Error(
				`API calls did not stop after ${MAX_WAITS} waits:\n${calls.join("\n")}`
			);
		}
		seen = calls.length;
	}
}
