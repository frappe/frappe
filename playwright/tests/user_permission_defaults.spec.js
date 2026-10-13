import { test, expect } from "../support";

test.describe("User-permission aware defaults", () => {
	// Regression: `frappe.defaults.get_user_defaults` must never return a default value
	// (e.g. the global default company) that the user is not permitted for, otherwise the
	// value gets auto-set on new documents and later fails the read/permission check.
	test("get_user_defaults drops values not permitted to the user", async ({ page, desk }) => {
		await page.goto("/desk");
		await desk.ready();

		const result = await page.evaluate(() => {
			const defaults = frappe.boot.user.defaults;
			const saved_defaults = {
				company: defaults["company"],
				Company: defaults["Company"],
			};
			const saved_perms = frappe.defaults._user_permissions;
			const result = {};

			try {
				// user is restricted to "_Allowed Co" but their (global) default is "_Denied Co"
				delete defaults["Company"];
				defaults["company"] = "_Denied Co";
				frappe.defaults._user_permissions = {
					Company: [{ doc: "_Allowed Co", applicable_for: null, is_default: 0 }],
				};
				result.denied = frappe.defaults.get_user_defaults("Company");

				defaults["company"] = "_Allowed Co";
				result.allowed = frappe.defaults.get_user_defaults("Company");

				frappe.defaults._user_permissions = {};
				defaults["company"] = "_Denied Co";
				result.unrestricted = frappe.defaults.get_user_defaults("Company");
			} finally {
				defaults["company"] = saved_defaults.company;
				defaults["Company"] = saved_defaults.Company;
				frappe.defaults._user_permissions = saved_perms;
			}
			return result;
		});

		// the disallowed default must be filtered out
		expect(result.denied).not.toContain("_Denied Co");
		// a permitted default is retained
		expect(result.allowed).toContain("_Allowed Co");
		// with no user permission on Company, the default is kept (nothing to restrict)
		expect(result.unrestricted).toContain("_Denied Co");
	});
});
