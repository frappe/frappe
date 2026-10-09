import path from "path";
import { test, expect } from "../support";
import { drop_file } from "../support/drop_file";

test.describe("Control Markdown Editor", () => {
	test("should allow inserting images by drag and drop", async ({ page, desk }) => {
		await page.goto("/desk/web-page/new");
		await desk.fill_field("content_type", "Markdown", "Select");
		const editor = desk.get_field("main_section_md", "Markdown Editor");
		await drop_file(
			editor,
			path.join(__dirname, "../fixtures/sample_image.jpg"),
			"image/jpeg"
		);
		await desk.click_modal_primary_button("Upload");
		await expect(editor).toContainText("![](/private/files/sample_image");
	});
});
