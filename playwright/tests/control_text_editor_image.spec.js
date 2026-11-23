import { test, expect } from "../support";

const DOCTYPE = "Test Text Editor Image";
const IMAGE = "/assets/frappe/images/frappe-framework-logo.png";

async function set_content(page, html) {
	await page.evaluate((html) => cur_frm.set_value("content", html), html);
}

test.describe("Text Editor images", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: DOCTYPE,
			fields: [{ label: "Content", fieldname: "content", fieldtype: "Text Editor" }],
		});
	});

	test("loads saved formatted content without errors", async ({ page, desk }) => {
		const errors = [];
		page.on("pageerror", (error) => errors.push(error.message));
		await desk.new_form(DOCTYPE);
		await set_content(
			page,
			`<div class="ql-editor read-mode"><p>Intro with <strong>bold</strong> text</p><p>Closing line</p></div>`
		);

		const editor = desk.get_field("content", "Text Editor");
		await expect(editor).toContainText("Closing line");
		await expect(editor.locator("span.ql-editor")).toHaveCount(0);
		expect(errors).toEqual([]);
	});

	test("resizes an image by dragging a corner", async ({ page, desk }) => {
		await desk.new_form(DOCTYPE);
		await set_content(page, `<p><img src="${IMAGE}" width="120"></p>`);

		const image = desk.get_field("content", "Text Editor").locator("img");
		await image.click();
		const handle = await page.locator(".ql-image-handle-se").boundingBox();
		await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
		await page.mouse.down();
		await page.mouse.move(handle.x + 60, handle.y, { steps: 5 });
		await page.mouse.up();

		await expect
			.poll(async () => Number(await image.getAttribute("width")))
			.toBeGreaterThan(150);
		const width = await image.getAttribute("width");
		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.content))
			.toContain(`width="${width}"`);
	});

	test("aligns an image with margins instead of float", async ({ page, desk }) => {
		await desk.new_form(DOCTYPE);
		await set_content(page, `<p><img src="${IMAGE}" width="120" style="float: left;"></p>`);

		const image = desk.get_field("content", "Text Editor").locator("img");
		await image.click();
		await page.getByRole("button", { name: "Align center" }).click();

		const centered = "display: block; margin-left: auto; margin-right: auto;";
		await expect(image).toHaveAttribute("style", centered);
		await expect.poll(() => page.evaluate(() => cur_frm.doc.content)).toContain(centered);

		await desk.save();
		await page.reload();
		await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");
		await expect(desk.get_field("content", "Text Editor").locator("img")).toHaveAttribute(
			"style",
			centered
		);
	});
});
