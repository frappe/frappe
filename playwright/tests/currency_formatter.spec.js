import { test, expect } from "../support";

test.describe("Currency Formatter", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/app/website");
		await desk.ready();
	});

	function format_amount(page, value, currency, defaults = {}) {
		return page.evaluate(
			([value, currency, defaults]) => {
				frappe.provide("locals.:Currency");
				locals[":Currency"]["BHD"] = {
					name: "BHD",
					number_format: "#,###.###",
					fraction_units: 1000,
					symbol: "BD",
				};
				locals[":Currency"]["AED"] = {
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
			},
			[value, currency, defaults]
		);
	}

	test("uses the row currency's number format when currency precision is not set", async ({
		page,
	}) => {
		expect(await format_amount(page, 97.646, "BHD")).toBe("BD 97.646");
		expect(await format_amount(page, 97.646, "AED")).toBe("AED 97.65");
	});

	test("uses currency precision over the row currency's number format", async ({ page }) => {
		expect(await format_amount(page, 97.646, "BHD", { currency_precision: 2 })).toBe(
			"BD 97.65"
		);
	});
});

test.describe("Currency Formatter outside desk", () => {
	test("resolves precision from system defaults on portal pages", async ({ page }) => {
		await page.goto("/me");

		const formatted = await page.evaluate(() => {
			Object.assign(frappe.sys_defaults, {
				currency: "USD",
				number_format: "#,###.##",
				currency_precision: 3,
				float_precision: 4,
			});

			return {
				currency: frappe.format(
					97.646,
					{ fieldtype: "Currency", fieldname: "amount" },
					{ only_value: true }
				),
				float: frappe.format(
					97.64646,
					{ fieldtype: "Float", fieldname: "qty" },
					{ only_value: true }
				),
			};
		});

		expect(formatted.currency).toBe("USD 97.646");
		expect(formatted.float).toBe("97.6465");
	});
});
