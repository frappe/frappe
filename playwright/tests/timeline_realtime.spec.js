import { test, expect } from "../support";
import { doc_room_joined } from "../support/realtime";

test.describe("Timeline Realtime Updates", () => {
	const doctype = "Test Autoincrement Comment";
	const route = "test-autoincrement-comment";
	// `.timeline-items` also matches the action bar above the feed
	const timeline = ".form-footer .timeline-items:not(.timeline-actions)";

	test.beforeAll(async ({ admin }) => {
		// `create_doctype` names its doctypes with `autoincrement`, so the
		// documents get integer names.
		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: doctype,
			fields: [
				{
					label: "Title",
					fieldname: "title",
					fieldtype: "Data",
					in_list_view: 1,
				},
			],
		});
	});

	test("shows a comment on an integer-named document without a reload", async ({
		page,
		api,
	}) => {
		const doc = await api.insert_doc(doctype, { title: "Realtime comment target" });
		// The whole point of this test: the document name is a number here, while
		// the route the form is opened with only ever carries its string form.
		expect(typeof doc.name).toBe("number");

		await page.goto(`/desk/${route}/${doc.name}`);
		await expect(page.locator(timeline)).toBeAttached();
		await page.waitForFunction(
			(room) => frappe.realtime.socket.connected && frappe.realtime.open_docs.has(room),
			`${doctype}:${doc.name}`
		);
		// Joining the doc room costs the server an async permission check, and the
		// event only reaches sockets already in the room.
		await doc_room_joined(page, api, doctype, doc.name);

		const content = `Realtime comment ${Date.now()}`;

		// Added over HTTP, so `docinfo_update` over the socket is the only
		// thing that can put this comment in the open form's timeline. The
		// server sends `reference_name` as an integer (the link validator
		// rewrites it with the name read back from the database), which the
		// listener has to match against the form's string `docname`.
		await api.call("frappe.desk.form.utils.add_comment", {
			reference_doctype: doctype,
			reference_name: String(doc.name),
			content: content,
			comment_email: "Administrator",
			comment_by: "Administrator",
		});

		await expect(page.locator(timeline)).toContainText(content, { timeout: 30000 });
		await expect(page.locator(".form-footer .comment-count")).toContainText("(1)");
	});
});
