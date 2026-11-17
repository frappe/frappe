import { test, expect } from "../support";

const METHOD = "/api/v2/method/frappe.desk.form.activity.get_activity_timeline";

// An app override or allowlist keyed to the method path applies only to this read.
test.describe("Desk v2 record timeline paging", () => {
	let todo;

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
	});

	test.afterAll(async ({ admin }) => {
		if (todo) await admin.remove_doc("ToDo", todo, true);
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("reads each page through the method path and loads older rows", async ({
		page,
		api,
		admin,
	}) => {
		todo = (await api.insert_doc("ToDo", { description: "timeline paging probe" })).name;
		for (let i = 0; i < 70; i++) {
			await admin.insert_doc("Comment", {
				comment_type: "Comment",
				reference_doctype: "ToDo",
				reference_name: todo,
				content: `<p>paging comment ${i}</p>`,
			});
		}

		const reads = [];
		const partReads = [];
		page.on("request", (request) => {
			const url = new URL(request.url());
			if (url.pathname === METHOD) reads.push(url.searchParams);
			if (/\/document\/ToDo\/[^/]+\/activity$/.test(url.pathname)) partReads.push(url.href);
		});
		await page.goto(`/apps/desk/todo/${todo}?tab=activity`);

		const comments = page.locator(".rich-text-view", { hasText: "paging comment" });
		await expect(comments.last()).toBeVisible();
		expect(reads[0].get("doctype")).toBe("ToDo");
		expect(reads[0].get("name")).toBe(todo);
		expect(reads[0].has("before")).toBe(false);

		// the newest page is one page short of every comment; the top of the feed reads the rest
		await expect.poll(() => comments.count()).toBeLessThan(70);
		await page
			.locator("[data-record-feed] [data-reka-scroll-area-viewport]")
			.evaluate((el) => {
				el.scrollTop = 0;
			});
		await expect.poll(() => comments.count(), { timeout: 15000 }).toBe(70);
		expect(reads.some((read) => read.has("before"))).toBe(true);
		expect(partReads).toEqual([]);
	});
});
