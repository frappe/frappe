// Checks control marks, accessible names and the shrinking gap list (frontend/act-gaps.json).
import { test, expect, ADMIN_PASSWORD, TEST_USER } from "../support";
import { Api } from "../support/api";
import {
	added_gaps,
	judge,
	find_problems,
	read_gaps,
	scan_dialog_acts,
	scan_menus,
	scan_row_menu,
	settle,
} from "../support/act_controls";
import { site_url } from "../support/config";

const SETTLE_MS = 1500;
const OPEN_MS = 400;

test.describe("Desk v2 act-backed controls", () => {
	test.skip(({ browserName }) => browserName !== "chromium", "One browser is enough");

	let request;
	let todo;
	let rule;
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
		// An Assignment Rule's record page has custom header buttons (frappe/automation/.../frontend/record.js).
		rule = "Act controls rule";
		// A run that stopped early leaves the rule behind: use it again.
		await api.insert_doc(
			"Assignment Rule",
			{
				name: rule,
				document_type: "Note",
				assign_condition: "public == 1",
				rule: "Round Robin",
				priority: 5,
				assignment_days: [{ day: "Monday" }],
				users: [{ user: "Administrator" }],
			},
			true
		);
		// "Load More" shows only past one page of 20, so the list always has a second.
		for (let i = 0; i < 21; i++) {
			const added = await api.call("frappe.tests.ui_test_helpers.create_todo", {
				description: `Act controls filler ${i}`,
			});
			filler.push(added.message.name);
		}
		// Only a row with a reference has a "Row actions" button. It is added last, so it is the first row.
		filler.push(
			(
				await api.insert_doc("ToDo", {
					description: "Act controls reference",
					reference_type: "User",
					reference_name: "Administrator",
				})
			).name
		);
	});

	test.afterAll(async () => {
		try {
			for (const name of [todo, ...filler]) {
				if (name) await new Api(request).remove_doc("ToDo", name, true);
			}
			if (rule) await new Api(request).remove_doc("Assignment Rule", rule, true);
		} finally {
			// The flag goes off even when a delete fails.
			if (request)
				await new Api(request).call("frappe.tests.ui_test_helpers.set_desk_v2", {
					enabled: 0,
				});
			await request?.dispose();
		}
	});

	test("the gap list has no entry the base branch lacks", () => {
		const added = added_gaps(read_gaps());
		test.skip(added === null, "The base branch has no gap list to compare with");
		expect(added, "act-gaps.json may only get shorter: fix the control instead.").toEqual([]);
	});

	// `menus` names the buttons that open a menu or popover without declaring it (`aria-haspopup` ones open anyway).
	for (const { kind, url, menus = [], bulk, shell, inherits, confirm } of [
		{ kind: "home", url: "/apps" },
		{ kind: "shell", url: "/apps/desk/todo/new", menus: ["Search"], shell: "only" },
		{ kind: "list", url: "/apps/desk/todo", menus: ["More", "Filter"], bulk: true },
		{ kind: "record", url: () => `/apps/desk/todo/${todo}`, menus: ["More actions"] },
		{ kind: "new", url: "/apps/desk/todo/new", menus: [] },
		// The editor has an act per field row: its confirmations are left out, they cost minutes.
		{ kind: "editor", url: "/apps/desk/doctype/ToDo", menus: [], confirm: false },
		// Frappe's own doctypes with custom header buttons: the UI workflow installs no other app.
		{
			kind: "assignment rule record",
			url: () => `/apps/desk/assignment-rule/${rule}`,
			menus: ["More actions"],
			inherits: ["record"],
		},
		{
			kind: "user permission list",
			url: "/apps/desk/user-permission",
			menus: ["More actions"],
			inherits: ["list"],
		},
	]) {
		test(`${kind} page`, async ({ page }) => {
			await page.goto(typeof url === "function" ? url() : url);
			await settle(page);
			// The shell is on every page: one test scans its menus and dialogs, on the page with the fewest controls of its own.
			const problems = shell ? [] : await find_problems(page);
			const scanned = await scan_menus(page, { extra: menus, shell });
			problems.push(...scanned.problems);
			for (const name of menus)
				expect(scanned.opened, `${kind}: no "${name}" button to open`).toContain(name);
			// Selecting rows adds the bulk acts, so the dialog acts run once, with the bar up.
			if (bulk) {
				problems.push(...(await scan_row_menu(page)));
				problems.push(...(await scan_bulk_bar(page)));
			}
			problems.push(
				...(await scan_dialog_acts(page, {
					shell: !!shell,
					restore: bulk ? select_rows : undefined,
					confirm,
				}))
			);
			report(kind, problems, inherits);
		});
	}
});

// The bulk-action bar shows once rows are selected; its menus and dialogs open from there.
async function select_rows(page) {
	await page.evaluate(async () => {
		const { rows } = await window.desk.state();
		await window.desk.acts.run("list.select", {
			names: rows.slice(0, 2).map((row) => row.name),
		});
	});
	await page.waitForTimeout(OPEN_MS);
}

async function scan_bulk_bar(page) {
	await select_rows(page);
	await page.waitForTimeout(SETTLE_MS);
	const problems = await find_problems(page);
	problems.push(...(await scan_menus(page, { scope: "[role=toolbar]" })).problems);
	return problems;
}

function report(kind, problems, inherits) {
	const { fresh, stale } = judge(kind, problems, read_gaps(), inherits);
	const lines = [
		...fresh.map((p) => `${kind}: "${p.control}" ${p.problem}. Give it a v-act or data-view.`),
		...stale.map(
			(control) =>
				`${kind}: "${control}" is fixed or gone: delete it from frontend/act-gaps.json.`
		),
	];
	expect(lines, lines.join("\n")).toEqual([]);
}
