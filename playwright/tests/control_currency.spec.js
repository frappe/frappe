import { test, expect } from "../support";

const fieldname = "currency_field";

const TEST_CASES = [
	{
		input: "10.101",
		df_options: { precision: 1 },
		blur_expected: "10.1",
	},
	{
		input: "10.101",
		df_options: { precision: "3" },
		blur_expected: "10.101",
	},
	{
		input: "10.101",
		df_options: { precision: "" },
		blur_expected: "10.10",
	},
	{
		input: "10.101",
		df_options: { precision: "0" },
		blur_expected: "10",
	},
	{
		input: "10.101",
		df_options: { precision: 0 },
		blur_expected: "10",
	},
	{
		input: "10.000",
		number_format: "#.###,##",
		df_options: { precision: 0 },
		blur_expected: "10.000",
	},
	{
		input: "10.000",
		number_format: "#.###,##",
		blur_expected: "10.000,00",
	},
	{
		input: "10.101",
		df_options: { precision: "" },
		blur_expected: "10.1",
		default_precision: 1,
	},
];

test.describe("Control Currency", () => {
	test("check value changes", async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();

		const input = desk.get_field(fieldname, "Currency");
		for (const test_case of TEST_CASES) {
			await page.evaluate((test_case) => {
				frappe.boot.sysdefaults.currency = test_case.currency;
				frappe.boot.sysdefaults.currency_precision = test_case.default_precision ?? 2;
				frappe.boot.sysdefaults.number_format = test_case.number_format ?? "#,###.##";
			}, test_case);

			await desk.dialog({
				title: "Currency Check",
				animate: false,
				fields: [
					{
						fieldname: fieldname,
						fieldtype: "Currency",
						Label: "Currency",
						...test_case.df_options,
					},
				],
			});
			await input.clear();
			await desk.fill_field(fieldname, test_case.input, "Currency");
			await input.blur();
			await expect(input).toHaveValue(test_case.blur_expected);
			await desk.hide_dialog();
		}
	});
});
