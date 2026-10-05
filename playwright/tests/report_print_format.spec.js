import { test, expect } from "../support";

const REPORT = "Test Print Format Report";
const JINJA_FORMAT = "Test Print Format Jinja";
const JS_FORMAT = "Test Print Format JS";

const jinja_method = "frappe.utils.print_format.render_report_jinja";
const pdf_method = "frappe.utils.print_format.report_to_pdf";

const is_post_to = (method) => (req) =>
	req.method() === "POST" && req.url().includes(`/api/method/${method}`);

const print_settings = (print_format) => ({
	orientation: "Landscape",
	with_letter_head: 0,
	print_format,
});

const stub_print_window = (page) =>
	page.evaluate(() => {
		window.__popups = 0;
		window.open = () => {
			window.__popups++;
			return {
				document: {
					write() {},
					close() {},
					getElementById: () => null,
					querySelector: () => null,
				},
			};
		};
	});

const popups = (page) => page.evaluate(() => window.__popups);

const print = (page, print_format) =>
	page.evaluate(
		(settings) => frappe.query_report.print_report(settings),
		print_settings(print_format)
	);

const download_pdf = (page, print_format) =>
	page.evaluate(
		(settings) => frappe.query_report.pdf_report(settings),
		print_settings(print_format)
	);

test.describe("Report Print Formats", () => {
	test.beforeAll(async ({ admin }) => {
		// the report selects from ToDo -- with no rows it renders empty and print is disabled
		for (const description of ["Print format row one", "Print format row two"]) {
			await admin.insert_doc("ToDo", { description }, true);
		}
		await admin.insert_doc(
			"Report",
			{
				report_name: REPORT,
				ref_doctype: "ToDo",
				report_type: "Query Report",
				is_standard: "No",
				query: "select name, status from `tabToDo` limit 5",
			},
			true
		);
		for (const [name, print_format_type] of [
			[JINJA_FORMAT, "Jinja"],
			[JS_FORMAT, "JS"],
		]) {
			await admin.insert_doc(
				"Print Format",
				{
					name,
					print_format_for: "Report",
					report: REPORT,
					print_format_type,
					standard: "No",
					custom_format: 1,
					html: "<h1>report body</h1>",
				},
				true
			);
		}
	});

	test.beforeEach(async ({ page }) => {
		await page.route(`**/api/method/${pdf_method}`, (route) =>
			route.fulfill({ status: 200, body: "" })
		);
		await page.goto(`/desk/query-report/${encodeURIComponent(REPORT)}`);
		await page.waitForFunction(
			(report) =>
				frappe.query_report?.report_name === report &&
				Array.isArray(frappe.query_report.filters) &&
				Array.isArray(frappe.query_report.columns) &&
				frappe.query_report.columns.length > 0,
			REPORT,
			{ timeout: 60000 }
		);
		await stub_print_window(page);
	});

	test("renders a jinja format on the server", async ({ page }) => {
		const jinja = page.waitForRequest(is_post_to(jinja_method));
		await print(page, JINJA_FORMAT);

		expect((await jinja).postDataJSON().print_format).toBe(JINJA_FORMAT);
		await expect.poll(() => popups(page)).toBe(1);
	});

	test("renders a js format in the browser", async ({ page }) => {
		const jinja_calls = [];
		page.on("request", (req) => is_post_to(jinja_method)(req) && jinja_calls.push(req));
		await print(page, JS_FORMAT);

		await expect.poll(() => popups(page)).toBe(1);
		expect(jinja_calls).toHaveLength(0);
	});

	test("sends the jinja body to the pdf service", async ({ page }) => {
		const jinja = page.waitForRequest(is_post_to(jinja_method));
		const pdf = page.waitForRequest(is_post_to(pdf_method));
		await download_pdf(page, JINJA_FORMAT);

		await jinja;
		await pdf;
	});
});
