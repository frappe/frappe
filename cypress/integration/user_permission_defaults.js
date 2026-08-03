context("User-permission aware defaults", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	// Regression: `frappe.defaults.get_user_defaults` must never return a default value
	// (e.g. the global default company) that the user is not permitted for, otherwise the
	// value gets auto-set on new documents and later fails the read/permission check.
	it("get_user_defaults drops values not permitted to the user", () => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				const defaults = frappe.boot.user.defaults;
				const saved_defaults = {
					company: defaults["company"],
					Company: defaults["Company"],
				};
				const saved_perms = frappe.defaults._user_permissions;

				try {
					// user is restricted to "_Allowed Co" but their (global) default is "_Denied Co"
					delete defaults["Company"];
					defaults["company"] = "_Denied Co";
					frappe.defaults._user_permissions = {
						Company: [{ doc: "_Allowed Co", applicable_for: null, is_default: 0 }],
					};

					// the disallowed default must be filtered out
					expect(frappe.defaults.get_user_defaults("Company")).to.not.include(
						"_Denied Co"
					);

					// a permitted default is retained
					defaults["company"] = "_Allowed Co";
					expect(frappe.defaults.get_user_defaults("Company")).to.include("_Allowed Co");

					// with no user permission on Company, the default is kept (nothing to restrict)
					frappe.defaults._user_permissions = {};
					defaults["company"] = "_Denied Co";
					expect(frappe.defaults.get_user_defaults("Company")).to.include("_Denied Co");
				} finally {
					defaults["company"] = saved_defaults.company;
					defaults["Company"] = saved_defaults.Company;
					frappe.defaults._user_permissions = saved_perms;
				}
			});
	});
});
