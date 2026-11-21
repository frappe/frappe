import { test, expect } from "../support";

const doctype = "Submit Message Row";
const submit_message = "Submit this document to confirm";

// Opened in place, so a handler registered first is there when the form is set up.
async function open_draft(page, desk, api, { hide }) {
	const doc = await api.insert_doc(doctype, { title: "draft" });
	await page.goto("/desk/todo");
	await desk.ready();

	await page.evaluate(
		([doctype, name, hide]) => {
			if (hide) {
				frappe.ui.form.on(doctype, {
					setup(frm) {
						frm.hide_submit_message = true;
					},
				});
			}
			frappe.set_route("Form", doctype, name);
		},
		[doctype, doc.name, hide]
	);
	await expect(page.locator(".primary-action[data-label='Submit']")).toBeVisible();
	return page.locator(".page-container:visible .form-message", { hasText: submit_message });
}

test.describe("Form submit message", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"DocType",
			{
				name: doctype,
				custom: 1,
				is_submittable: 1,
				module: "Custom",
				fields: [{ fieldname: "title", fieldtype: "Data", label: "Title" }],
				permissions: [
					{
						role: "System Manager",
						read: 1,
						write: 1,
						create: 1,
						delete: 1,
						submit: 1,
						cancel: 1,
					},
				],
			},
			true
		);
	});

	test("asks to submit a saved draft", async ({ page, desk, api }) => {
		const message = await open_draft(page, desk, api, { hide: false });
		await expect(message).toBeVisible();
	});

	test("leaves the message out when the form sets hide_submit_message", async ({
		page,
		desk,
		api,
	}) => {
		const message = await open_draft(page, desk, api, { hide: true });
		await expect(message).toHaveCount(0);
	});
});
