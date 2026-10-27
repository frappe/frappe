import { test, expect } from "../support";

const test_button_names = [
	"Metallica",
	"Pink Floyd",
	"Porcupine Tree (the GOAT)",
	"AC / DC",
	`Electronic Dance "music"`,
	"l'imperatrice",
];

const add_button = (page, label, group = "TestGroup") =>
	page.evaluate(
		([label, group]) => {
			cur_frm.add_custom_button(label, () => {}, group);
		},
		[label, group]
	);

const check_button_count = async (page, label, group = "TestGroup") => {
	const viewport = page.viewportSize();

	await page.getByRole("button", { name: group, exact: true }).click();
	const item = page.locator(`[data-label="${encodeURIComponent(label)}"]`);
	await expect(item).toHaveCount(1);
	await expect(item).toBeVisible();
	await page.keyboard.press("Escape");

	await page.setViewportSize({ width: 420, height: 900 });
	const dropdown_btn_label = `${group} > ${label}`;
	await page.locator(".menu-btn-group > .btn").click();
	const dropdown_item = page.locator(`[data-label="${encodeURIComponent(dropdown_btn_label)}"]`);
	await expect(dropdown_item).toHaveCount(1);
	await expect(dropdown_item).toBeVisible();
	await page.keyboard.press("Escape");

	await page.setViewportSize(viewport);
};

test.describe("Custom group button behaviour on desk", () => {
	test.beforeEach(async ({ desk }) => {
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
});
