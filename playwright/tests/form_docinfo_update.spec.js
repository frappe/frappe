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
			const reference = { reference_doctype: "ToDo", reference_name: name };
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
			const share = { ...reference, name: "share-row", user: "Guest", read: 1 };
			send({ doc: share, key: "shared", action: "add" });
			send({ doc: share, key: "shared", action: "add" });
			const shared = frappe.model.docinfo.ToDo[name].shared;
			return { errors, shares: shared.filter((row) => row.name === "share-row").length };
		}, todo.name);

		expect(result.errors).toEqual([]);
		expect(result.shares).toBe(1);

		await api.remove_doc("ToDo", todo.name, true);
	});
});
