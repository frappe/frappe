import { test, expect } from "../support";

const REPORT = "Test Print Format Report";
const JINJA_FORMAT = "Test Print Format Jinja";
const JS_FORMAT = "Test Print Format JS";

const PRINT_PAGE = "#page-report-print";

const jinja_method = "frappe.utils.print_format.render_report_jinja";
const pdf_method = "frappe.utils.print_format.report_to_pdf";

const is_post_to = (method) => (req) =>
	req.method() === "POST" && req.url().includes(`/api/method/${method}`);

const open_print_view = (page, print_format) =>
	page.goto(
		`/desk/report-print/${encodeURIComponent(REPORT)}?print_format=${encodeURIComponent(
			print_format
		)}`
	);

const preview = (page) => page.frameLocator(`${PRINT_PAGE} .preview-beta-wrapper iframe`);

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

	test("opens the print view from the report menu", async ({ page, desk }) => {
		await page.goto(`/desk/query-report/${encodeURIComponent(REPORT)}`);
		await page.waitForFunction(
			(report) =>
				frappe.query_report?.report_name === report && frappe.query_report.data?.length,
			REPORT,
			{ timeout: 60000 }
		);
		await page.locator("#page-query-report .page-actions .menu-btn-group > button").click();
		await desk.click_menu_item("Print");

		await expect(page).toHaveURL(/\/report-print\//);
		await expect(preview(page).locator(".print-format table")).toBeVisible();
	});

	test("renders a jinja format on the server", async ({ page }) => {
		const jinja = page.waitForRequest(is_post_to(jinja_method));
		await open_print_view(page, JINJA_FORMAT);

		expect((await jinja).postDataJSON().print_format).toBe(JINJA_FORMAT);
		await expect(preview(page).locator("h1")).toHaveText("report body");
	});

	test("renders a js format in the browser", async ({ page }) => {
		const jinja_calls = [];
		page.on("request", (req) => is_post_to(jinja_method)(req) && jinja_calls.push(req));
		await open_print_view(page, JS_FORMAT);

		await expect(preview(page).locator("h1")).toHaveText("report body");
		expect(jinja_calls).toHaveLength(0);
	});

	test("sends the previewed format to the pdf service", async ({ page }) => {
		await page.route(`**/api/method/${pdf_method}`, (route) =>
			route.fulfill({ status: 200, body: "" })
		);
		await open_print_view(page, JINJA_FORMAT);
		await expect(preview(page).locator("h1")).toHaveText("report body");

		const pdf = page.waitForRequest(is_post_to(pdf_method));
		await page.locator(`${PRINT_PAGE} [data-original-title="Download PDF"]`).click();

		expect((await pdf).postData()).toContain("report body");
	});
});
