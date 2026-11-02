import fs from "fs";
import path from "path";
import { test, expect } from "../support";

const example_file = path.join(__dirname, "../fixtures/example.json");

async function open_upload_dialog(page, desk) {
	await page.evaluate(() => {
		new frappe.ui.FileUploader();
	});
	await page.waitForFunction(() => window.cur_dialog && cur_dialog.$wrapper.is(":visible"));
	return desk.get_open_dialog();
}

async function drop_example_file(page, dialog) {
	const content = fs.readFileSync(example_file).toString("base64");
	const data_transfer = await page.evaluateHandle((content) => {
		const data_transfer = new DataTransfer();
		const bytes = Uint8Array.from(atob(content), (char) => char.charCodeAt(0));
		data_transfer.items.add(new File([bytes], "example.json", { type: "application/json" }));
		return data_transfer;
	}, content);
	await dialog.locator(".file-upload-area").dispatchEvent("drop", {
		dataTransfer: data_transfer,
	});
}

const wait_for_upload = (page) =>
	page.waitForResponse(
		(res) => res.request().method() === "POST" && res.url().includes("/api/method/upload_file")
	);

test.describe("FileUploader", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/app");
		await expect(page).toHaveURL(/\/app\/.+/);
		await desk.ready();
	});

	test("upload dialog api works", async ({ page, desk }) => {
		const dialog = await open_upload_dialog(page, desk);
		await expect(dialog).toContainText("Drag and drop files");
		await desk.hide_dialog();
	});

	test("should accept dropped files", async ({ page, desk }) => {
		const dialog = await open_upload_dialog(page, desk);

		await drop_example_file(page, dialog);

		await expect(dialog.locator(".file-name")).toContainText("example.json");
		const upload_file = wait_for_upload(page);
		await dialog.getByRole("button", { name: "Upload", exact: true }).click();
		expect((await upload_file).status()).toBe(200);
		await expect(page.locator(".modal:visible")).toHaveCount(0);
	});

	test("should accept uploaded files", async ({ page, desk, api }) => {
		const uploaded = await page.request.post("/api/method/upload_file", {
			headers: await api.headers(),
			multipart: {
				file: {
					name: "example.json",
					mimeType: "application/json",
					buffer: fs.readFileSync(example_file),
				},
				is_private: "1",
			},
		});
		expect(uploaded.status()).toBe(200);

		const dialog = await open_upload_dialog(page, desk);

		await dialog.getByRole("button", { name: "Library", exact: true }).click();
		await page
			.getByPlaceholder("Search by filename or extension", { exact: true })
			.pressSequentially("example.json");
		await desk.get_open_dialog().getByText("example.json", { exact: true }).first().click();
		const upload_file = wait_for_upload(page);
		await desk.get_open_dialog().getByRole("button", { name: "Upload", exact: true }).click();
		const response = await (await upload_file).json();
		expect(response.message).toHaveProperty("file_name", "example.json");
		await expect(page.locator(".modal:visible")).toHaveCount(0);
	});
});
