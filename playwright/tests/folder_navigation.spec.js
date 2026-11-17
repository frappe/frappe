import { test, expect } from "../support";

const file_url = "https://example.com/files/72402.jpg";

async function remove_test_folders(admin) {
	const files = await admin.get_list(
		"File",
		["name"],
		[["folder", "=", "Home/Attachments/Test Folder"]]
	);
	for (const file of files.data) {
		await admin.remove_doc("File", file.name);
	}
	await admin.remove_doc("File", "Home/Attachments/Test Folder", true);
	await admin.remove_doc("File", "Home/Test Folder", true);
}

async function create_folder(page, desk, name) {
	const created = page.waitForResponse((res) =>
		res.url().includes("/api/method/frappe.core.api.file.create_new_folder")
	);
	await desk.click_menu_button("New Folder");
	await desk.fill_field("value", name);
	await desk.click_modal_primary_button("Create");
	expect((await created).status()).toBe(200);
}

async function delete_row(page, desk, name) {
	const deleted = page.waitForResponse((res) =>
		res.url().includes("/api/method/frappe.desk.reportview.delete_items")
	);
	await page.locator(`.list-row-checkbox[data-name="${name}"]`).check();
	await desk.click_action_button("Delete");
	await desk.click_modal_primary_button("Yes");
	expect((await deleted).status()).toBe(200);
}

test.describe("Folder Navigation", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ admin }) => {
		await remove_test_folders(admin);
	});

	test.afterAll(async ({ admin }) => {
		await remove_test_folders(admin);
	});

	test("Adding Folders", async ({ page, desk }) => {
		await page.goto("/app/List/File/Home");
		await desk.ready();

		await create_folder(page, desk, "Test Folder");
		await expect(
			page.locator(`.list-row-checkbox[data-name="Home/Test Folder"]`)
		).toBeVisible();
	});

	test("Navigating the nested folders, checking if the URL formed is correct, checking if the added content in the child folder is correct", async ({
		page,
		desk,
	}) => {
		await page.goto("/app/List/File/Home/Attachments");
		await desk.ready();

		await create_folder(page, desk, "Test Folder");

		await page.goto("/app/List/File/Home/Attachments/Test%20Folder");
		await desk.ready();

		const uploaded = page.waitForResponse((res) =>
			res.url().includes("/api/method/upload_file")
		);
		await page.getByRole("button", { name: "Add File" }).first().click();
		await page.locator(".file-uploader").getByText("Link", { exact: true }).click();
		await page.locator(".input-group > input.form-control:visible").fill(file_url);
		await desk.click_modal_primary_button("Upload");
		expect((await uploaded).status()).toBe(200);

		await page.goto("/app/List/File/Home/Attachments");
		await expect(page.locator("span.level-item > a > span").first()).toBeVisible();
		await expect(page.locator("span.level-item > a > span")).toContainText(["Test Folder"]);

		await page.goto("/app/List/File/Home/Attachments/Test%20Folder");
		const row = page.locator(".list-row-container").first();
		await expect(row).toContainText("72402.jpg");
		const file_name = await row.locator(".list-row-checkbox").getAttribute("data-name");

		await delete_row(page, desk, file_name);

		await page.goto("/app/List/File/Home/Attachments");
		await delete_row(page, desk, "Home/Attachments/Test Folder");
	});

	test("Deleting Test Folder from the home", async ({ page, desk, api }) => {
		await page.goto("/app/List/File/Home");
		await delete_row(page, desk, "Home/Test Folder");
		const folders = await api.get_list("File", ["name"], [["name", "=", "Home/Test Folder"]]);
		expect(folders.data).toHaveLength(0);
	});
});
