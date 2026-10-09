import { test, expect } from "../support";

const test_button_names = [
	"Metallica",
	"Pink Floyd",
	"Porcupine Tree (the GOAT)",
	"AC / DC",
	`Electronic Dance "music"`,
	"l'imperatrice",
];

const exact_text = (text) =>
	new RegExp(`^\\s*${text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`);

const add_button = (page, label, group = "TestGroup") =>
	page.evaluate(
		([label, group]) => {
			cur_frm.add_custom_button(label, () => {}, group);
		},
		[label, group]
	);

const check_button_count = async (page, label, group = "TestGroup") => {
	const viewport = page.viewportSize();
	const menu_items = page.locator('.es-menu [role="menuitem"]');

	await expect(page.locator(`[data-label="${encodeURIComponent(label)}"]`)).toHaveCount(1);
	await page.getByRole("button", { name: group, exact: true }).click();
	const item = menu_items.filter({ hasText: exact_text(label) });
	await expect(item).toHaveCount(1);
	await expect(item).toBeVisible();
	await page.keyboard.press("Escape");

	await page.setViewportSize({ width: 420, height: 900 });
	const dropdown_btn_label = `${group} > ${label}`;
	await expect(
		page.locator(`[data-label="${encodeURIComponent(dropdown_btn_label)}"]`)
	).toHaveCount(1);
	await page.locator(".menu-btn-group > button").click();
	const group_item = menu_items.filter({ hasText: exact_text(group) });
	await expect(group_item).toHaveCount(1);
	await group_item.click();
	const nested_item = menu_items.filter({ hasText: exact_text(label) });
	await expect(nested_item).toHaveCount(1);
	await expect(nested_item).toBeVisible();
	await page.keyboard.press("Escape");

	await page.setViewportSize(viewport);
};

const click_frappe_call_button = async (page, label, call_opts) => {
	const button = page.locator(`button[data-label="${encodeURIComponent(label)}"]`);
	const call = page.waitForResponse((res) =>
		res.url().endsWith(`/api/method/${call_opts.method}`)
	);
	await page.evaluate(
		([label, call_opts]) => {
			cur_frm.add_custom_button(label, () => frappe.call(call_opts));
		},
		[label, call_opts]
	);
	await button.click();
	const response = await call;
	await expect(button).toBeEnabled();
	return response;
};

test.describe("Custom group button behaviour on desk", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.addInitScript(() => {
			window.localStorage.setItem("sidebar-expanded", "false");
		});
		await desk.new_form("Note");
	});

	for (const button_name of test_button_names) {
		test(`Custom button works with name '${button_name}'`, async ({ page }) => {
			await add_button(page, button_name);
			await check_button_count(page, button_name);

			await add_button(page, button_name);
			await check_button_count(page, button_name);
		});
	}

	test("Clears the busy state when the callback returns a frappe.call", async ({ page }) => {
		await click_frappe_call_button(page, "Deferred Button", {
			method: "frappe.auth.get_logged_user",
		});
	});

	test("Clears the busy state when the frappe.call fails", async ({ page }) => {
		const response = await click_frappe_call_button(page, "Failing Deferred Button", {
			method: "frappe.client.get",
			args: { doctype: "Note", name: "does-not-exist" },
		});
		expect(response.status()).toBe(404);
	});
});
