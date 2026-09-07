context("Currency Formatter", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
	});

	function format_amount(value, currency, defaults = {}) {
		return cy.window().then((win) => {
			const frappe = win.frappe;
			frappe.provide("locals.:Currency");
			win.locals[":Currency"]["BHD"] = {
				name: "BHD",
				number_format: "#,###.###",
				fraction_units: 1000,
				symbol: "BD",
			};
			win.locals[":Currency"]["AED"] = {
				name: "AED",
				number_format: "#,###.##",
				fraction_units: 100,
				symbol: "AED",
			};

			const applied = {
				currency: "AED",
				number_format: "#,###.##",
				currency_precision: "",
				use_number_format_from_currency: 1,
				...defaults,
			};
			Object.assign(frappe.boot.sysdefaults, applied);
			Object.assign(frappe.boot.user.defaults, applied);

			return frappe.format(
				value,
				{ fieldtype: "Currency", fieldname: "amount", options: "currency" },
				{ only_value: true },
				{ currency: currency }
			);
		});
	}

	it("uses the row currency's number format when currency precision is not set", () => {
		format_amount(97.646, "BHD").should("eq", "BD 97.646");
		format_amount(97.646, "AED").should("eq", "AED 97.65");
	});

	it("uses currency precision over the row currency's number format", () => {
		format_amount(97.646, "BHD", { currency_precision: 2 }).should("eq", "BD 97.65");
	});
});

context("Currency Formatter outside desk", () => {
	before(() => {
		// Any website page carries the web boot and frappe.format, but a signed-in user is
		// redirected off /login and into desk, which boots frappe much later. Drop the session the
		// first suite established - the spec does not isolate tests - then assert the page really
		// is the portal one before reading anything off it.
		Cypress.session.clearAllSavedSessions();
		cy.clearCookies();
		cy.visit("/login");
		cy.location("pathname").should("eq", "/login");
	});

	it("resolves precision from system defaults on portal pages", () => {
		cy.window().then((win) => {
			Object.assign(win.frappe.sys_defaults, {
				currency: "USD",
				number_format: "#,###.##",
				currency_precision: 3,
				float_precision: 4,
			});

			expect(
				win.frappe.format(
					97.646,
					{ fieldtype: "Currency", fieldname: "amount" },
					{ only_value: true }
				)
			).to.eq("USD 97.646");
			expect(
				win.frappe.format(
					97.64646,
					{ fieldtype: "Float", fieldname: "qty" },
					{ only_value: true }
				)
			).to.eq("97.6465");
		});
	});
});
