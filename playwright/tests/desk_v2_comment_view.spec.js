import { test, expect } from "../support";

const PROBE = [
	"<p>probe comment</p>",
	'<img src="/missing.png" onerror="window.__commentXss = \'img\'">',
	"<script>window.__commentXss = 'script'</script>",
	"<style>body { display: none }</style>",
	'<a href="https://example.com" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 9999">cover</a>',
	'<form action="https://example.com"><input name="pwd"><button formaction="https://example.com">Go</button></form>',
	'<pre><code class="language-javascript">function add(a, b) {\n\treturn a + b;\n}</code></pre>',
].join("");

test.describe("Desk v2 comment view", () => {
	let todo;

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
	});

	test.afterAll(async ({ admin }) => {
		if (todo) await admin.remove_doc("ToDo", todo, true);
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("draws a saved comment sanitised, without the editor", async ({ page, api, admin }) => {
		todo = (await api.insert_doc("ToDo", { description: "comment view probe" })).name;
		const comment = await admin.insert_doc("Comment", {
			comment_type: "Comment",
			reference_doctype: "ToDo",
			reference_name: todo,
			content: "<p>placeholder</p>",
		});
		// Save-time sanitising would strip the probe; an old or imported row skips it.
		await admin.call("frappe.tests.ui_test_helpers.db_set_values", {
			doctype: "Comment",
			name: comment.name,
			values: { content: PROBE },
		});

		const editorChunks = [];
		page.on("request", (request) => {
			if (/\/editor-[\w-]+\.js$/.test(request.url())) editorChunks.push(request.url());
		});
		await page.goto(`/apps/desk/todo/${todo}?tab=activity`);

		const view = page.locator(".rich-text-view", { hasText: "probe comment" });
		await expect(view).toBeVisible();
		await expect(view.locator("img")).toHaveJSProperty("complete", true);
		await expect(view.locator("img")).not.toHaveAttribute("onerror");
		await expect(view.locator("script, style")).toHaveCount(0);
		expect(await page.evaluate(() => window.__commentXss)).toBeUndefined();
		await expect(page.locator("body")).toBeVisible();

		await expect(view.locator("form, [formaction]")).toHaveCount(0);
		const cover = view.getByRole("link", { name: "cover" });
		await expect(cover).toHaveAttribute("target", "_blank");
		const coversTheSidebar = await cover.evaluate((link) =>
			link.contains(document.elementFromPoint(5, 5))
		);
		expect(coversTheSidebar).toBe(false);

		await expect(view.locator("pre .hljs-keyword").first()).toHaveText("function");
		await expect(view.locator("pre .code-block-lines > span")).toHaveText(["1", "2", "3"]);
		await expect(page.locator(".ProseMirror")).toHaveCount(0);
		expect(editorChunks).toEqual([]);
	});
});
