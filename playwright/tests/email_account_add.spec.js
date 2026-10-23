import { test, expect } from "../support";

const CONNECT =
	"**/api/method/frappe.integrations.frappe_providers.email_oauth.initiate_mailbox_connect";

async function open_add_dialog(page, desk) {
	await desk.go_to_list("ToDo");
	await desk.ready();
	// boot is read when the Email Account list is first made, so set it before routing there
	await page.evaluate(() => {
		frappe.boot.is_v2_site = 1;
		frappe.boot.one_click_email_services = { "Outlook.com": "Outlook" };
		frappe.set_route("List", "Email Account");
	});
	await expect(page.locator("body")).toHaveAttribute("data-route", "List/Email Account/List");
	await page.locator(".primary-action:visible").click();
	return page.locator(".modal:visible", { hasText: "Choose your email provider" });
}

test("offers the manual form when Outlook sign-in isn't available", async ({ page, desk }) => {
	let request_body;
	await page.route(CONNECT, (route) => {
		request_body = route.request().postData();
		return route.fulfill({ json: {} });
	});

	const dialog = await open_add_dialog(page, desk);
	const primary = dialog.locator(".btn-modal-primary");
	await expect(primary).toBeDisabled();

	await dialog.getByRole("button", { name: "Outlook" }).click();
	await expect(dialog.locator(".btn-modal-secondary")).toHaveText("Set up manually");
	await primary.click();

	await expect(
		dialog.getByText(
			"Outlook sign-in isn't available right now. You can still set it up manually."
		)
	).toBeVisible();
	expect(request_body).toContain("Outlook.com");
	await expect(dialog.locator(".btn-modal-secondary")).toBeHidden();
	await expect(primary).toHaveText("Set up manually");

	await primary.click();
	await expect(page.locator("body")).toHaveAttribute(
		"data-route",
		/^Form\/Email Account\/new-email-account-/
	);
	await expect(desk.get_field("service", "Select")).toHaveValue("Outlook.com");
});
