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
