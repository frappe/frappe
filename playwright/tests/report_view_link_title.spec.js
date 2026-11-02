import { test, expect } from "../support";
import custom_link_title_doctype from "../fixtures/custom_link_title_doctype";

const doctype_name = custom_link_title_doctype.name;

test.describe("Report View Link Titles", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", custom_link_title_doctype, true);
		await admin.insert_doc(
			doctype_name,
			{
				title: "Renewal Reminder",
				display_name: "Renewal reminder for Contoso",
			},
			true
		);
		await admin.insert_doc(
			doctype_name,
			{
				title: "Contract Follow Up",
				display_name: "Contract follow up",
				parent_entry: "Renewal Reminder",
			},
			true
		);
	});

	test("skips the link title lookup for a blank Link column", async ({ page }) => {
		const requested_docnames = [];
		page.on("request", (request) => {
			if (
				request.method() === "POST" &&
				request.url().includes("/api/method/frappe.desk.search.get_link_title")
			) {
				requested_docnames.push(new URLSearchParams(request.postData()).get("docname"));
			}
		});
		const link_title = page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.desk.search.get_link_title")
		);

		await page.goto(`/app/List/${doctype_name}/Report`);
		await link_title;

		expect(requested_docnames).not.toContain("null");
		expect(requested_docnames).toContain("Renewal Reminder");
	});
});
