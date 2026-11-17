// Fails when a visible button or menu item on a desk v2 page has neither `data-act` (an act the page can run)
// nor `data-view`, or when a button has no accessible name. `frontend/act-gaps.json` lists the controls
// still to fix: it may only get shorter, so a gap that no longer fails must be deleted.
import { test, expect, ADMIN_PASSWORD, TEST_USER } from "../support";
import { Api } from "../support/api";
import { judge, find_problems, read_gaps } from "../support/act_controls";
import { site_url } from "../support/config";

const SETTLE_MS = 1500;

test.describe("Desk v2 act-backed controls", () => {
	test.skip(({ browserName }) => browserName !== "chromium", "One browser is enough");

	let request;
	let todo;
	const filler = [];

	test.beforeAll(async ({ playwright }, workerInfo) => {
		request = await playwright.request.newContext({
			baseURL: site_url(workerInfo.parallelIndex),
		});
		const res = await request.post("/api/method/login", {
			data: { usr: TEST_USER, pwd: ADMIN_PASSWORD },
		});
		expect(res.status(), `login: ${await res.text()}`).toBe(200);
		const api = new Api(request);
		await api.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		todo = (
			await api.call("frappe.tests.ui_test_helpers.create_todo", {
				description: "Check the act controls",
			})
		).message.name;
		// "Load More" shows only past one page of 20, so the list always has a second.
		for (let i = 0; i < 21; i++) {
			const added = await api.call("frappe.tests.ui_test_helpers.create_todo", {
				description: `Act controls filler ${i}`,
			});
			filler.push(added.message.name);
		}
	});

	test.afterAll(async () => {
		for (const name of [todo, ...filler]) {
			if (name) await new Api(request).remove_doc("ToDo", name, true);
		}
		if (request)
			await new Api(request).call("frappe.tests.ui_test_helpers.set_desk_v2", {
				enabled: 0,
			});
		await request?.dispose();
	});

	for (const [kind, url, steps] of [
		["home", "/apps", []],
		["list", "/apps/desk/todo", [more_menu, open_palette, open_user_menu]],
		["record", () => `/apps/desk/todo/${todo}`, [more_actions_menu]],
		["new", "/apps/desk/todo/new", []],
		["editor", "/apps/desk/doctype/ToDo", []],
	]) {
		test(`${kind} page`, async ({ page }) => {
			await page.goto(typeof url === "function" ? url() : url);
			await settle(page);
			const problems = await find_problems(page);
			for (const step of steps) {
				await step(page);
				problems.push(...(await find_problems(page)));
				await page.keyboard.press("Escape");
			}
			report(kind, problems);
		});
	}
});

async function settle(page) {
	await page.waitForFunction(() => window.desk);
	await page.waitForFunction(async () => !(await window.desk.state()).loading);
	await page.waitForTimeout(SETTLE_MS);
}

async function more_menu(page) {
	await page.getByRole("button", { name: "More", exact: true }).click();
}

async function more_actions_menu(page) {
	await page.getByRole("button", { name: "More actions", exact: true }).first().click();
}

async function open_palette(page) {
	await page.getByRole("button", { name: "Search", exact: true }).first().click();
}

async function open_user_menu(page) {
	await page.locator("button[data-key=user-menu]:visible").first().click();
}

function report(kind, problems) {
	const { fresh, stale } = judge(kind, problems, read_gaps());
	const lines = [
		...fresh.map((p) => `${kind}: "${p.control}" ${p.problem}. Give it a v-act or data-view.`),
		...stale.map(
			(control) =>
				`${kind}: "${control}" is fixed or gone: delete it from frontend/act-gaps.json.`
		),
	];
	expect(lines, lines.join("\n")).toEqual([]);
}
