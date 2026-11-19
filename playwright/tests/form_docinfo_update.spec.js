import { test, expect } from "../support";

test.describe("Form docinfo updates", () => {
	test("skips the keys desk v2 also publishes and adds a row once", async ({ page, api }) => {
		const todo = await api.insert_doc("ToDo", { description: "Docinfo listener target" });

		await page.goto(`/desk/todo/${todo.name}`);
		await page.waitForFunction(
			(name) => Array.isArray(frappe.model.docinfo?.ToDo?.[name]?.shared),
			todo.name
		);

		const result = await page.evaluate((name) => {
			const errors = [];
			const send = (payload) => {
				for (const listener of frappe.realtime.socket.listeners("docinfo_update")) {
					try {
						listener(payload);
					} catch (error) {
						errors.push(`${payload.key}: ${error.message}`);
					}
				}
			};
			const docinfo = frappe.model.docinfo.ToDo[name];
			const reference = { reference_doctype: "ToDo", reference_name: name };
			const tags = docinfo.tags;
			const shared = JSON.stringify(docinfo.shared);
			send({
				doc: { ...reference, name: "tag-row", tag: "urgent" },
				key: "tags",
				action: "add",
			});
			send({
				doc: { ...reference, name: "favourite-row", user: frappe.session.user },
				key: "favourites",
				action: "add",
			});
			send({
				doc: { ...reference, name: "share-row", user: "Guest", read: 1 },
				key: "shared",
				action: "add",
			});
			const comment = {
				...reference,
				doctype: "Comment",
				name: "comment-row",
				comment_type: "Comment",
				comment_email: frappe.session.user,
				owner: frappe.session.user,
				content: "Docinfo listener comment",
				creation: frappe.datetime.now_datetime(),
			};
			send({ doc: comment, key: "comments", action: "add" });
			send({ doc: comment, key: "comments", action: "add" });
			return {
				errors,
				tags_unchanged: docinfo.tags === tags,
				has_favourites: "favourites" in docinfo,
				shared_unchanged: JSON.stringify(docinfo.shared) === shared,
				comments: docinfo.comments.filter((row) => row.name === "comment-row").length,
			};
		}, todo.name);

		expect(result.errors).toEqual([]);
		expect(result.tags_unchanged).toBe(true);
		expect(result.has_favourites).toBe(false);
		expect(result.shared_unchanged).toBe(true);
		expect(result.comments).toBe(1);

		await api.remove_doc("ToDo", todo.name, true);
	});
});
