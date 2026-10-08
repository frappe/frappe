import { test, expect, TEST_USER } from "../support";

test.describe.skip("Permissions API", () => {
	const set_system_manager = (admin, action) =>
		admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action,
			user: TEST_USER,
			role: "System Manager",
		});

	test.beforeAll(async ({ admin }) => {
		await set_system_manager(admin, "remove");
	});

	test.afterAll(async ({ admin }) => {
		await set_system_manager(admin, "add");
	});

	test("Checks permissions via `has_perm` for Kanban Board DocType", async ({ page }) => {
		await page.goto("/desk/kanban-board/view/list");
		const perms = await page.evaluate(
			() =>
				new Promise((resolve) =>
					frappe.model.with_doctype("Kanban Board", () =>
						resolve({
							read: frappe.perm.has_perm("Kanban Board", 0, "read"),
							write: frappe.perm.has_perm("Kanban Board", 0, "write"),
							print: frappe.perm.has_perm("Kanban Board", 0, "print"),
						})
					)
				)
		);
		expect(perms).toEqual({ read: true, write: true, print: false });
	});

	test("Checks permissions via `get_perm` for Kanban Board DocType", async ({ page }) => {
		await page.goto("/desk/kanban-board/view/list");
		const perms = await page.evaluate(
			() =>
				new Promise((resolve) =>
					frappe.model.with_doctype("Kanban Board", () =>
						resolve(frappe.perm.get_perm("Kanban Board"))
					)
				)
		);
		expect(perms.read).toBe(true);
		expect(perms.write).toBe(true);
		expect(perms.rights_without_if_owner).toContain("read");
	});
});

test.describe("Permissions before a doctype's meta is loaded", () => {
	test("Resolves delete for ToDo before its meta is loaded", async ({ page, desk }) => {
		await page.goto("/desk");
		await desk.ready();

		const before = await page.evaluate(() => {
			delete locals.DocType["ToDo"];
			delete frappe.perm.doctype_perm["ToDo"];

			return {
				has_meta: Boolean(frappe.get_meta("ToDo")),
				can_delete: frappe.perm.has_perm("ToDo", 0, "delete"),
			};
		});
		expect(before).toEqual({ has_meta: false, can_delete: true });

		const after = await page.evaluate(
			() =>
				new Promise((resolve) =>
					frappe.model.with_doctype("ToDo", () =>
						resolve({
							has_meta: Boolean(frappe.get_meta("ToDo")),
							can_delete: frappe.perm.has_perm("ToDo", 0, "delete"),
						})
					)
				)
		);
		expect(after).toEqual({ has_meta: true, can_delete: true });
	});
});
