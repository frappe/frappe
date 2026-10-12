import { test, expect } from "../support";

const pdf_route = "**/api/method/frappe.utils.print_format.report_to_pdf";

function render_pdf(page) {
	return page.evaluate(() =>
		frappe.render_pdf("<h1>Stock Balance</h1>", { report_name: "stock_balance.pdf" })
	);
}

function wait_for_pdf_request(page) {
	return page.waitForRequest(
		(req) => req.method() === "POST" && req.url().includes("report_to_pdf")
	);
}

test.describe("Render PDF", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
	});

	test("freezes the page while the PDF is generated", async ({ page }) => {
		let respond;
		const held = new Promise((resolve) => (respond = resolve));
		await page.route(pdf_route, async (route) => {
			await held;
			await route.fulfill({ status: 504, body: "" });
		});

		const pdf = page.waitForResponse((res) => res.url().includes("report_to_pdf"));
		await render_pdf(page);

		await expect(page.locator("#freeze .freeze-message")).toContainText("Generating PDF...");
		respond();
		await pdf;
		await expect(page.locator("#freeze")).toHaveCount(0);
	});

	test("reports a gateway timeout as a size problem", async ({ page }) => {
		await page.route(pdf_route, (route) => route.fulfill({ status: 504, body: "" }));

		const pdf = page.waitForResponse((res) => res.url().includes("report_to_pdf"));
		await render_pdf(page);
		await pdf;

		await expect(page.locator(".msgprint-dialog .modal-title")).toContainText(
			"Could not generate PDF"
		);
		await expect(page.locator(".msgprint")).toContainText("may be too large");
	});

	test("points at the Error Log when the server fails for another reason", async ({ page }) => {
		await page.route(pdf_route, (route) => route.fulfill({ status: 500, body: "" }));

		const pdf = page.waitForResponse((res) => res.url().includes("report_to_pdf"));
		await render_pdf(page);
		await pdf;

		await expect(page.locator(".msgprint")).toContainText("Check the Error Log for details.");
	});

	test("shows the server message when the response carries one", async ({ page }) => {
		await page.route(pdf_route, (route) =>
			route.fulfill({
				status: 417,
				json: {
					_server_messages: JSON.stringify([
						JSON.stringify({ message: "Report is too large to render" }),
					]),
				},
			})
		);

		const pdf = page.waitForResponse((res) => res.url().includes("report_to_pdf"));
		await render_pdf(page);
		await pdf;

		await expect(page.locator(".msgprint")).toContainText("Report is too large to render");
	});

	test("does not blame report size when the connection drops", async ({ page }) => {
		await page.route(pdf_route, (route) => route.abort());

		const pdf = wait_for_pdf_request(page);
		await render_pdf(page);
		await pdf;

		await expect(page.locator(".msgprint")).toContainText("Check your connection");
		await expect(page.locator("#freeze")).toHaveCount(0);
	});
});
