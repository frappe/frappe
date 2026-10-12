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
		await desk.login("Administrator");
		await page.goto("/desk");
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

	test.describe("Public file upload restriction", () => {
		const test_user = "test_file_uploader@example.com";
		const test_password = "test_password";
		const setting = "only_allow_system_managers_to_upload_public_files";
		let original_setting;

		const set_restriction = (admin, value) =>
			admin.set_value("System Settings", "System Settings", { [setting]: value });

		const open_desk_with_restriction = async (page, desk, value) => {
			await page.goto("/desk");
			await desk.ready();
			await page.evaluate(
				([setting, value]) => {
					frappe.boot.sysdefaults[setting] = value;
				},
				[setting, value]
			);
		};

		const open_dialog_with_file = async (page, desk) => {
			const dialog = await open_upload_dialog(page, desk);
			await drop_example_file(page, dialog);
			await expect(dialog.locator(".file-preview")).toBeAttached();
			return dialog;
		};

		test.beforeAll(async ({ admin }) => {
			original_setting = (await admin.get_doc("System Settings", "System Settings")).data[
				setting
			];
			await admin.call("frappe.tests.ui_test_helpers.create_test_user", {
				username: test_user,
			});
			await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
				action: "remove",
				user: test_user,
				role: "System Manager",
			});
			await admin.set_value("User", test_user, { new_password: test_password });
		});

		test.afterAll(async ({ admin }) => {
			await set_restriction(admin, original_setting);
			await admin.remove_doc("User", test_user, true);
		});

		test("should show checkbox and toggle when setting is disabled for System Manager", async ({
			page,
			desk,
			admin,
		}) => {
			await set_restriction(admin, 0);
			await open_desk_with_restriction(page, desk, 0);

			const dialog = await open_dialog_with_file(page, desk);

			await expect(dialog.locator("#uploader-private-checkbox")).toBeVisible();
			await expect(dialog.locator("#uploader-private-checkbox input")).toBeEnabled();

			const toggle_button = dialog.locator(".modal-footer .btn-modal-secondary");
			await expect(toggle_button).toBeVisible();
			await expect(toggle_button).toContainText("Set all");

			await desk.hide_dialog();
		});

		test("should show checkbox and toggle when setting is disabled for non-System Manager", async ({
			page,
			desk,
			admin,
		}) => {
			await set_restriction(admin, 0);

			await desk.login(test_user, test_password);
			await open_desk_with_restriction(page, desk, 0);

			const dialog = await open_dialog_with_file(page, desk);

			await expect(dialog.locator("#uploader-private-checkbox")).toBeVisible();
			await expect(dialog.locator("#uploader-private-checkbox input")).toBeEnabled();

			const toggle_button = dialog.locator(".modal-footer .btn-modal-secondary");
			await expect(toggle_button).toBeVisible();
			await expect(toggle_button).toContainText("Set all");

			await desk.hide_dialog();
		});

		test("should show checkbox and toggle when setting is enabled for System Manager", async ({
			page,
			desk,
			admin,
		}) => {
			await set_restriction(admin, 1);
			await open_desk_with_restriction(page, desk, 1);

			const dialog = await open_dialog_with_file(page, desk);

			await expect(dialog.locator("#uploader-private-checkbox")).toBeVisible();
			await expect(dialog.locator("#uploader-private-checkbox input")).toBeEnabled();

			const toggle_button = dialog.locator(".modal-footer .btn-modal-secondary");
			await expect(toggle_button).toBeVisible();
			await expect(toggle_button).toContainText("Set all");

			await desk.hide_dialog();
		});

		test("should show disabled checkbox and hide toggle when setting is enabled for non-System Manager", async ({
			page,
			desk,
			admin,
		}) => {
			await set_restriction(admin, 1);

			await desk.login(test_user, test_password);
			await open_desk_with_restriction(page, desk, 1);

			const dialog = await open_dialog_with_file(page, desk);

			await expect(dialog.locator("#uploader-private-checkbox")).toBeVisible();
			await expect(dialog.locator("#uploader-private-checkbox input")).toBeDisabled();

			await expect(dialog.locator(".modal-footer .btn-modal-secondary")).toBeHidden();

			await desk.hide_dialog();
		});
	});
});
