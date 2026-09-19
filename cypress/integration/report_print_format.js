context("Report Print Formats", () => {
	const REPORT = "Test Print Format Report";
	const JINJA_FORMAT = "Test Print Format Jinja";
	const JS_FORMAT = "Test Print Format JS";

	const jinja_route = "/api/method/frappe.utils.print_format.render_report_jinja";
	const pdf_route = "/api/method/frappe.utils.print_format.report_to_pdf";

	const print_settings = (print_format) => ({
		orientation: "Landscape",
		with_letter_head: 0,
		print_format,
	});

	// print_report opens a window; hand it a stub so the run stays in one tab
	const stub_print_window = () =>
		cy.window().then((win) => {
			cy.stub(win, "open")
				.returns({
					document: {
						write() {},
						close() {},
						getElementById: () => null,
						querySelector: () => null,
					},
				})
				.as("popup");
		});

	const print = (print_format) =>
		cy
			.window()
			.then((win) => win.frappe.query_report.print_report(print_settings(print_format)));

	const download_pdf = (print_format) =>
		cy
			.window()
			.then((win) => win.frappe.query_report.pdf_report(print_settings(print_format)));

	before(() => {
		cy.login();
		// insert_doc reads frappe.csrf_token off the window, so load the app first
		cy.visit("/app/todo");
		cy.insert_doc(
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
			cy.insert_doc(
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

	beforeEach(() => {
		cy.intercept("POST", jinja_route).as("jinja");
		cy.intercept("POST", pdf_route, { statusCode: 200, body: "" }).as("pdf");

		cy.visit(`/app/query-report/${encodeURIComponent(REPORT)}`);
		// report_name is set on route; printing also needs the filters and a finished run
		cy.window({ timeout: 60000 }).its("frappe.query_report.report_name").should("eq", REPORT);
		cy.window({ timeout: 60000 }).its("frappe.query_report.filters").should("be.an", "array");
		cy.window({ timeout: 60000 }).its("frappe.query_report.data").should("be.an", "array");
		stub_print_window();
	});

	it("renders a jinja format on the server", () => {
		print(JINJA_FORMAT);

		cy.wait("@jinja").its("request.body.report_name").should("eq", REPORT);
		cy.get("@popup").should("have.been.called");
	});

	it("renders a js format in the browser", () => {
		print(JS_FORMAT);

		// the print window proves the flow ran, so the absent call is meaningful
		cy.get("@popup").should("have.been.called");
		cy.get("@jinja.all").should("have.length", 0);
	});

	it("sends the jinja body to the pdf service", () => {
		download_pdf(JINJA_FORMAT);

		cy.wait("@jinja");
		cy.wait("@pdf");
	});
});
