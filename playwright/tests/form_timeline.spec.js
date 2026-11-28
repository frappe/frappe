import { test, expect } from "../support";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";
import doctype_with_child_table from "../fixtures/doctype_with_child_table";

// `.timeline-items` also matches the action bar above the feed
const timeline = ".form-footer .timeline-items:not(.timeline-actions)";
const entry = `${timeline} > .timeline-item`;
const comment = (name) => `${entry}[data-doctype="Comment"][data-name="${name}"]`;

test.describe("Form Timeline", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", child_table_doctype, true);
		await admin.insert_doc("DocType", child_table_doctype_1, true);
		await admin.insert_doc("DocType", doctype_with_child_table, true);
	});

	const new_todo = (api) =>
		api.insert_doc("ToDo", { description: `Timeline test ${Date.now()}` });

	const open_form = async (page, route, name) => {
		await page.goto(`/desk/${route}/${encodeURIComponent(name)}`);
		await expect(page.locator(`${entry}`).first()).toBeAttached();
	};

	const add_comment = async (api, todo, content) =>
		(
			await api.call("frappe.desk.form.utils.add_comment", {
				reference_doctype: "ToDo",
				reference_name: todo.name,
				content,
				comment_email: "frappe@example.com",
				comment_by: "Frappe",
			})
		).message;

	const choose_menu_item = (page, label) =>
		page.locator(".es-menu[data-state=open] .es-menu__item", { hasText: label }).click();

	const open_comment_menu = async (page, name, label) => {
		await page.locator(`${comment(name)} .more-actions > .action-btn`).click();
		await choose_menu_item(page, label);
	};

	test("shows a single field change inline and several in a box", async ({ page, api }) => {
		const todo = await new_todo(api);
		await api.call("frappe.client.set_value", {
			doctype: "ToDo",
			name: todo.name,
			fieldname: "priority",
			value: "High",
		});
		await api.call("frappe.client.set_value", {
			doctype: "ToDo",
			name: todo.name,
			fieldname: { priority: "Low", description: "Changed description" },
		});
		await open_form(page, "todo", todo.name);

		const single = page.locator(entry, { hasText: "changed Priority from" });
		await expect(single.locator(".timeline-change-new")).toContainText("High");
		await expect(single.locator("a.timeline-version-link")).toHaveAttribute(
			"href",
			/\/version\//
		);

		const box = page
			.locator(entry, { hasText: "changed 2 fields" })
			.locator(".timeline-changes");
		await expect(box).toBeVisible();
		await expect(box).toContainText("Priority");
		await expect(box.locator(".timeline-changes-more-toggle")).toHaveCount(0);
	});

	test("folds a long list of changes behind Show all changes", async ({ page, api }) => {
		const todo = await new_todo(api);
		await api.call("frappe.client.set_value", {
			doctype: "ToDo",
			name: todo.name,
			fieldname: {
				status: "Closed",
				priority: "High",
				date: "2030-01-15",
				color: "#ff0000",
				description: "Seven fields at once",
				role: "System Manager",
			},
		});
		await open_form(page, "todo", todo.name);

		const box = page
			.locator(entry, { hasText: "changed 6 fields" })
			.locator(".timeline-changes");
		await expect(box.locator(".timeline-change-row:visible")).toHaveCount(5);
		const toggle = box.locator(".timeline-changes-more-toggle");
		await expect(toggle).toHaveText("Show all changes");
		await toggle.click();
		await expect(box.locator(".timeline-change-row:visible")).toHaveCount(6);
		await expect(toggle).toHaveText("Show fewer");
		await expect(toggle).toHaveAttribute("aria-expanded", "true");
	});

	test("names added rows and shows their fields on demand", async ({ page, api }) => {
		const doc = await api.insert_doc(doctype_with_child_table.name, {
			title: `Timeline rows ${Date.now()}`,
			child_table: [{ title: `First row ${Date.now()}` }],
		});
		const row_title = `Added row ${Date.now()}`;
		await api.update_doc(doctype_with_child_table.name, doc.name, {
			child_table_1: [{ data: row_title, check: 1, date: "2030-01-15" }],
		});
		await open_form(page, "doctype-with-child-table", doc.name);

		const added = page.locator(entry, { hasText: `added ${row_title} to Child Table 1` });
		await expect(added).toBeVisible();
		const toggle = added.locator(".timeline-changes-toggle");
		const details = added.locator(".timeline-changes");
		await expect(details).toBeHidden();
		await toggle.click();
		await expect(details).toBeVisible();
		await expect(details).toContainText("Check");
		await expect(details).toContainText("Yes");
		await expect(toggle).toHaveText("Hide");
	});

	test("groups files attached together into one entry", async ({ page, api }) => {
		const todo = await new_todo(api);
		for (const n of ["first", "second", "third"]) {
			await api.call("frappe.client.insert", {
				doc: {
					doctype: "File",
					file_name: `a-rather-long-attachment-name-${n}.txt`,
					content: `content of the ${n} file`,
					attached_to_doctype: "ToDo",
					attached_to_name: todo.name,
				},
			});
		}
		// narrow enough that the chips can't all fit on one line
		await page.setViewportSize({ width: 480, height: 900 });
		await open_form(page, "todo", todo.name);

		const group = page.locator(entry, { hasText: "attached 3 files" });
		await group.scrollIntoViewIfNeeded();
		await expect(group.locator(".timeline-file")).toHaveCount(3);
		const more = group.locator(".timeline-file-more");
		await expect(more).toBeVisible();
		await expect(more).toContainText("more");
		await more.click();
		await expect(group.locator(".timeline-file-list")).toHaveClass(/expanded/);
		await expect(more).toHaveAttribute("aria-expanded", "true");
		await expect(group.locator(".timeline-file:visible")).toHaveCount(3);
	});

	test("shows one kind of activity per tab, with an empty state", async ({ page, api }) => {
		const todo = await new_todo(api);
		await add_comment(api, todo, "A comment to filter by");
		await open_form(page, "todo", todo.name);
		const tab = (name) => page.locator(".timeline-filters").getByRole("radio", { name });

		await tab("Comments").click();
		await expect(tab("Comments")).toHaveAttribute("aria-checked", "true");
		await expect(page.locator(`${entry}:visible`)).toHaveCount(1);
		await expect(page.locator(`${entry}:visible`)).toContainText("A comment");

		await tab("Emails").click();
		const empty = page.locator(".timeline-empty-state");
		await expect(empty).toBeVisible();
		await expect(empty).toContainText("No emails yet");
		await empty.getByRole("button", { name: "Show all" }).click();

		await expect(empty).toHaveCount(0);
		await expect(tab("All")).toHaveAttribute("aria-checked", "true");
		expect(await page.locator(`${entry}:visible`).count()).toBeGreaterThan(1);
	});

	test("adds a comment from the Add menu", async ({ page, api }) => {
		const todo = await new_todo(api);
		await open_form(page, "todo", todo.name);
		const box = page.locator(".timeline-comment-box");
		await expect(box).toBeHidden();

		await page.locator(".timeline-add-menu").click();
		await choose_menu_item(page, "Comment");
		const send = page.locator(".timeline-comment-send");
		await expect(send).toBeDisabled();
		await box.locator(".ql-editor").fill("Hello from the Add menu");
		await expect(send).toBeEnabled();
		await send.click();

		const posted = page.locator(entry, { hasText: "Hello from the Add menu" });
		await expect(posted).toBeVisible({ timeout: 30000 });
		await expect(posted.locator(".timeline-you")).toContainText("You");
		await expect(box).toBeHidden();
		await expect(page.locator(".form-footer .comment-count")).toContainText("(1)");
	});

	test("edits one comment at a time", async ({ page, api }) => {
		const todo = await new_todo(api);
		const first = await add_comment(api, todo, "First comment");
		const second = await add_comment(api, todo, "Second comment");
		await open_form(page, "todo", todo.name);

		await open_comment_menu(page, first.name, "Edit");
		await expect(
			page.locator(`${comment(first.name)} .timeline-message-card-editing`)
		).toBeVisible();

		await open_comment_menu(page, second.name, "Edit");
		await expect(page.locator(".timeline-message-card-editing")).toHaveCount(1);
		const editing = page.locator(`${comment(second.name)} .timeline-message-card-editing`);
		await editing.locator(".ql-editor").fill("Second comment, edited");
		await editing.getByRole("button", { name: "Save" }).click();

		await expect(page.locator(".es-toast", { hasText: "Comment updated" })).toBeVisible();
		await expect(page.locator(comment(second.name))).toContainText("Second comment, edited", {
			timeout: 30000,
		});
		await expect(page.locator(".timeline-message-card-editing")).toHaveCount(0);
	});

	test("switches editors while a live update waits", async ({ page, api }) => {
		const todo = await new_todo(api);
		const first = await add_comment(api, todo, "First comment");
		const second = await add_comment(api, todo, "Second comment");
		await open_form(page, "todo", todo.name);

		await open_comment_menu(page, first.name, "Edit");
		// a live update while editing waits until the editor closes
		await add_comment(api, todo, "Arrived while editing");
		await page.evaluate(() => cur_frm.timeline.refresh());

		await open_comment_menu(page, second.name, "Edit");
		const editing = page.locator(`${comment(second.name)} .timeline-message-card-editing`);
		await expect(editing).toBeVisible();
		await editing.getByRole("button", { name: "Cancel" }).click();
		await expect(page.locator(entry, { hasText: "Arrived while editing" })).toBeVisible();
	});

	test("deletes a comment with undo", async ({ page, api }) => {
		const todo = await new_todo(api);
		const doc = await add_comment(api, todo, "A comment to delete");
		await open_form(page, "todo", todo.name);

		await open_comment_menu(page, doc.name, "Delete");
		await expect(page.locator(comment(doc.name))).toBeHidden();
		await page
			.locator(".es-toast", { hasText: "Comment deleted" })
			.locator(".es-toast__action")
			.click();
		await expect(page.locator(comment(doc.name))).toBeVisible();

		await open_comment_menu(page, doc.name, "Delete");
		await expect
			.poll(
				async () =>
					(
						await api.call("frappe.client.get_count", {
							doctype: "Comment",
							filters: { name: doc.name },
						})
					).message,
				{ timeout: 15000 }
			)
			.toBe(0);
	});

	test("shows the start of a long comment", async ({ page, api }) => {
		const todo = await new_todo(api);
		const long = Array.from({ length: 60 }, (_, i) => `<p>Line ${i + 1}</p>`).join("");
		const doc = await add_comment(api, todo, long);
		await open_form(page, "todo", todo.name);

		const content = page.locator(`${comment(doc.name)} .content`);
		await expect(content).toHaveClass(/timeline-content-clamped/);
		const more = page.locator(`${comment(doc.name)} .timeline-message-more`);
		await more.click();
		await expect(content).not.toHaveClass(/timeline-content-clamped/);
		await expect(more).toHaveText("Show less");
	});

	test("groups consecutive views of a document", async ({ page, api }) => {
		const event = await api.insert_doc("Event", {
			subject: `Timeline views ${Date.now()}`,
			starts_on: "2026-01-01 10:00:00",
			event_type: "Public",
		});
		for (let i = 0; i < 3; i++) await open_form(page, "event", event.name);

		const views = page.locator(entry, { hasText: "viewed this" });
		await expect(views).toHaveCount(1);
		await expect(views).toContainText(/You viewed this \d+ times/);
	});
});
