import fs from "fs";
import path from "path";
import { test, expect } from "../support";

const sample_image = fs
	.readFileSync(path.join(__dirname, "../fixtures", "sample_image.jpg"))
	.toString("base64");

test.describe("Form sidebar image", () => {
	const new_contact = async (api, with_image = true) => {
		const contact = await api.insert_doc("Contact", {
			first_name: `Image test ${Date.now()}`,
		});
		if (!with_image) return contact;
		const file = (
			await api.call("frappe.client.insert", {
				doc: {
					doctype: "File",
					file_name: `contact-${Date.now()}.jpg`,
					content: sample_image,
					decode: 1,
					is_private: 0,
					attached_to_doctype: "Contact",
					attached_to_name: contact.name,
				},
			})
		).message;
		return api.update_doc("Contact", contact.name, { image: file.file_url });
	};

	const open_contact = async (page, contact) => {
		await page.goto(`/desk/contact/${encodeURIComponent(contact.name)}`);
		await expect(page.locator(".sidebar-image-section")).toBeVisible();
	};

	test("opens the image in a viewer", async ({ page, api }) => {
		const contact = await new_contact(api);
		await open_contact(page, contact);

		await page.getByRole("button", { name: "View image" }).click();
		const viewer = page.locator(".sidebar-image-viewer .modal-content");
		await expect(viewer.locator(".sidebar-image-viewer-image")).toHaveAttribute(
			"src",
			contact.image
		);
		await expect(viewer).toContainText(contact.full_name || contact.first_name);
		await expect(viewer.getByRole("button", { name: "Download" })).toBeVisible();
		await expect(viewer.getByRole("button", { name: "Change" })).toBeVisible();

		// bootstrap ignores Escape while the modal is still fading in
		await expect(async () => {
			await page.keyboard.press("Escape");
			await expect(page.locator(".sidebar-image-viewer")).toHaveCount(0, { timeout: 1000 });
		}).toPass();
	});

	test("changes or removes the image from the camera button", async ({ page, api }) => {
		const contact = await new_contact(api);
		await open_contact(page, contact);

		await page.getByRole("button", { name: "Change image" }).click();
		const menu = page.locator(".es-menu[data-state=open]");
		await expect(menu).toContainText("Change image");
		await expect(page.locator(".sidebar-image-viewer")).toHaveCount(0);
		await menu.locator(".es-menu__item", { hasText: "Remove image" }).click();

		await page.locator(".modal.show").getByRole("button", { name: "Yes" }).click();
		await expect(page.locator(".sidebar-standard-image")).toBeVisible();
		await expect(page.getByRole("button", { name: "Add image" })).toBeVisible();
		await expect(page.locator(".sidebar-image-edit")).toBeHidden();
	});

	test("removes the image from the viewer", async ({ page, api }) => {
		const contact = await new_contact(api);
		await open_contact(page, contact);

		await page.getByRole("button", { name: "View image" }).click();
		await page
			.locator(".sidebar-image-viewer")
			.getByRole("button", { name: "Remove" })
			.click();
		await page.locator(".modal.show").getByRole("button", { name: "Yes" }).click();
		await expect(page.locator(".sidebar-standard-image")).toBeVisible();
	});

	test("uploads straight away when there is no image", async ({ page, api }) => {
		const contact = await new_contact(api, false);
		await open_contact(page, contact);

		await expect(page.locator(".sidebar-image-edit")).toBeHidden();
		const add = page.getByRole("button", { name: "Add image" });
		await add.hover();
		await expect(add.locator(".sidebar-image-add")).toBeVisible();
		await add.click();
		await expect(page.locator(".modal.show .file-upload-area")).toBeVisible();
		await expect(page.locator(".sidebar-image-viewer")).toHaveCount(0);
	});

	test("shows only the initials on a new record", async ({ page }) => {
		await page.goto("/desk/contact/new");
		await expect(page.locator(".sidebar-standard-image")).toBeAttached();
		await expect(page.locator(".sidebar-image-preview")).not.toHaveAttribute("role");
		await expect(page.locator(".sidebar-image-edit")).toBeHidden();
	});
});
