import { test, expect } from "../support";

const CRUMBS = ".navbar-breadcrumbs:visible li";

async function expect_trail(page, expected) {
	await expect
		.poll(() =>
			page.locator(CRUMBS).evaluateAll((items) => items.map((li) => li.textContent.trim()))
		)
		.toEqual(expected);
}

// The print view's main section holds only an iframe, which has no text of its own.
async function print_view_ready(page) {
	await page.waitForFunction(
		() => window.frappe && frappe.app && frappe.request.ajax_count === 0
	);
	await expect(page.locator(".layout-main-section:visible > *").first()).toBeAttached();
}

test.describe("Breadcrumbs", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.setup_tree_doctype");
	});

	test.beforeEach(async ({ page }) => {
		await page.addInitScript(() => {
			window.trail_of = (root) =>
				Array.from(root.querySelectorAll(".navbar-breadcrumbs li"), (li) =>
					li.textContent.trim()
				);
		});
	});

	test("names a list once", async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
		await expect_trail(page, ["To Do"]);
	});

	test("leads a document back to its list", async ({ page, desk, api }) => {
		const doc = await api.insert_doc("ToDo", { description: "crumb test todo" }, true);
		await page.goto(`/desk/todo/${doc.name}`);
		await desk.ready();
		await expect(page.locator(CRUMBS).first().locator("a")).toHaveAttribute(
			"href",
			"/desk/todo"
		);
		await expect(page.locator(CRUMBS).last().locator("a")).toHaveCount(0);
	});

	test("does not repeat the document name over its doctype", async ({ page, desk }) => {
		await page.goto("/desk/doctype/ToDo");
		await desk.ready();
		await expect_trail(page, ["DocType", "ToDo"]);
	});

	test("names a doctype that has a page of its own", async ({ page, desk, api }) => {
		await api.insert_doc(
			"Print Format",
			{ name: "Crumb Format", doc_type: "ToDo", standard: "No" },
			true
		);
		await page.goto("/desk/print-format-builder/Crumb Format");
		await desk.ready();
		await expect_trail(page, ["Print Format", "Crumb Format"]);
	});

	test("keeps the document reachable from the print view", async ({ page, api }) => {
		const doc = await api.insert_doc("ToDo", { description: "crumb print todo" }, true);
		await page.goto(`/desk/print/ToDo/${doc.name}`);
		await print_view_ready(page);
		await expect(page.locator(CRUMBS)).toHaveCount(3);
		await expect(page.locator(CRUMBS).last()).toContainText("Print");
		await expect(page.locator(CRUMBS).nth(1).locator("a")).toHaveAttribute(
			"href",
			`/desk/todo/${doc.name}`
		);
	});

	test("names a tree by its tree title", async ({ page }) => {
		await page.goto("/desk/custom-tree/view/tree");
		await expect(page.locator('.tree-link[data-label="All Trees"]')).toBeVisible();
		await expect_trail(page, ["Custom Tree Tree"]);
	});

	test("names a workspace without linking it to itself", async ({ page, desk }) => {
		await page.goto("/desk/build");
		await desk.ready();
		await expect(page.locator(CRUMBS)).toHaveCount(1);
		await expect(page.locator(CRUMBS).locator("a")).toHaveCount(0);
	});

	test("still draws through the retired API", async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
		await expect_trail(page, ["To Do"]);

		const result = await page.evaluate(() => {
			const warn = console.warn;
			let warnings = 0;
			console.warn = () => {
				warnings += 1;
			};

			const b = frappe.breadcrumbs;
			const trail = () => window.trail_of(frappe.container.page);
			const result = {};

			try {
				result.current_page_is_container_page =
					frappe.get_current_page() === frappe.container.page.page;

				b.clear();
				result.cleared = trail();

				b.$breadcrumbs.append('<li><a href="/desk/workflow">Workflow</a></li>');
				result.appended_markup = trail();

				b.clear();
				b.append_breadcrumb_element("/desk/todo", "To Do");
				b.set_custom_breadcrumbs({ label: "Custom", route: "/desk/x" });
				result.custom = trail();

				b.clear();
				b.set_list_breadcrumb({ doctype: "ToDo" });
				result.list = trail();

				b.clear();
				b.add({ type: "Custom", label: "Print Format", route: "/desk/print-format" });
				result.added = trail();
				b.append_breadcrumb_element("", "Standard");
				result.appended_once = trail();
				b.append_breadcrumb_element("", "Third");
				result.appended_twice = trail();

				b.clear();
				b.set_list_breadcrumb({ doctype: "ToDo" });

				b.toggle(false);
				result.toggled_off = trail();
				b.toggle(true);
				result.toggled_on = trail();

				b.clear();
				b.all[frappe.get_route_str()] = { module: "Desk", doctype: "ToDo" };
				b.update();
				result.registry = trail();

				result.current_page = b.current_page();
			} finally {
				console.warn = warn;
			}
			result.warnings = warnings;
			return result;
		});

		expect(result.current_page_is_container_page).toBe(true);
		expect(result.cleared).toEqual([]);
		expect(result.appended_markup).toEqual(["Workflow"]);
		expect(result.custom).toEqual(["To Do", "Custom"]);
		expect(result.list).toEqual(["ToDo"]);
		expect(result.added).toEqual(["Print Format"]);
		expect(result.appended_once).toEqual(["Print Format", "Standard"]);
		expect(result.appended_twice).toEqual(["Print Format", "Standard", "Third"]);
		expect(result.toggled_off).toEqual([]);
		expect(result.toggled_on).toEqual(["ToDo"]);
		expect(result.registry).toEqual(["ToDo"]);
		expect(result.current_page).toBe("List/ToDo/List");
		expect(result.warnings).toBeGreaterThan(0);
	});

	test("cannot reach a page that is not on screen through the retired API", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/todo");
		await desk.ready();
		await expect_trail(page, ["To Do"]);

		const result = await page.evaluate(() => {
			const detached = $("<div>");
			const off_screen = frappe.ui.make_app_page({
				parent: detached,
				single_column: true,
			});
			off_screen.set_breadcrumbs([{ label: "Off screen" }]);

			frappe.breadcrumbs.clear();
			frappe.breadcrumbs.append_breadcrumb_element("/desk/x", "Landed here");

			return {
				on_screen: window.trail_of(frappe.container.page),
				off_screen: window.trail_of(detached[0]),
			};
		});

		expect(result.on_screen).toEqual(["Landed here"]);
		expect(result.off_screen).toEqual(["Off screen"]);
	});

	test("draws no trail for a form inside a dialog", async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
		await expect_trail(page, ["To Do"]);

		const crumbs_in_dialog = await page.evaluate(
			() =>
				new Promise((resolve) => {
					frappe.model.with_doctype("ToDo", () => {
						const dialog = new frappe.ui.Dialog({ title: "probe" });
						const $host = $("<div>").appendTo(dialog.$body);
						dialog.show();

						const frm = new frappe.ui.form.Form("ToDo", $host.get(0), false);
						frm.in_dialog = true;
						frm.refresh(frappe.model.make_new_doc_and_get_name("ToDo"));

						setTimeout(() => {
							const count = $host.find(".navbar-breadcrumbs li").length;
							dialog.hide();
							resolve(count);
						}, 800);
					});
				})
		);
		expect(crumbs_in_dialog).toBe(0);

		await expect_trail(page, ["To Do"]);
	});

	test("ignores a page that is not on screen", async ({ page, desk }) => {
		await page.goto("/desk/permission-manager");
		await desk.ready();
		await expect_trail(page, ["Role Permissions Manager"]);

		const result = await page.evaluate(() => {
			const detached = $("<div>");
			const off_screen = frappe.ui.make_app_page({
				parent: detached,
				single_column: true,
			});
			off_screen.set_breadcrumbs([
				{ label: "Sales Invoice" },
				{ label: "New Sales Invoice" },
			]);

			return {
				off_screen: window.trail_of(detached[0]),
				is_container_page: frappe.container.page === detached[0],
			};
		});

		expect(result.off_screen).toEqual(["Sales Invoice", "New Sales Invoice"]);
		expect(result.is_container_page).toBe(false);

		await expect_trail(page, ["Role Permissions Manager"]);
	});
});
