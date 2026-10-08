import { test, expect } from "../support";

const escape_regex = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const containing = (text) => new RegExp(escape_regex(text));
const with_class = (name) => new RegExp(`(^|\\s)${escape_regex(name)}(\\s|$)`);

const explorer_group = (page, title) =>
	page.locator(".explorer-group", { hasText: containing(title) }).first();
const menu_item = (page, label) =>
	page.locator(".es-menu__item", { hasText: containing(label) }).first();

async function show(page, component) {
	await page.evaluate(
		(component) => frappe.pages["component-explorer"].render_component(component),
		component
	);
	await expect(page.locator(`.explorer-groups[data-component="${component}"]`)).toBeAttached();
}

test.describe("Espresso components", () => {
	test.beforeEach(async ({ page }) => {
		await page.goto("/desk/component-explorer");
		await expect(page.locator(".explorer-groups[data-component]")).toBeAttached();
	});

	test.describe("Dropdown", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Dropdown");
		});

		test("toggles open and closed on trigger click", async ({ page }) => {
			const trigger = explorer_group(page, "Basic actions")
				.locator('[aria-haspopup="menu"]')
				.first();

			await trigger.click();
			await expect(page.locator(".es-menu[data-state='open']")).toBeAttached();

			await trigger.click();
			await expect(page.locator(".es-menu[data-state='open']")).toHaveCount(0);
		});

		test("opens on ArrowDown onto the first row, and Escape closes + returns focus to the trigger", async ({
			page,
		}) => {
			const trigger = explorer_group(page, "Basic actions")
				.locator('[aria-haspopup="menu"]')
				.first();

			await trigger.dispatchEvent("keydown", { key: "ArrowDown" });
			await expect(page.locator(".es-menu[data-state='open']")).toBeAttached();
			await expect(page.locator(".es-menu__item[data-highlighted]")).toHaveCount(1);

			await page
				.locator(".es-menu__item[data-highlighted]")
				.dispatchEvent("keydown", { key: "Escape" });
			await expect(page.locator(".es-menu[data-state='open']")).toHaveCount(0);
			await expect(trigger).toBeFocused();
		});

		test("closes on Escape after a mouse open — the panel holds focus, so the cursor's position doesn't matter", async ({
			page,
		}) => {
			const trigger = explorer_group(page, "Basic actions")
				.locator('[aria-haspopup="menu"]')
				.first();

			await trigger.click();
			await expect(page.locator(".es-menu[data-state='open']")).toBeFocused();

			await page.locator(":focus").dispatchEvent("keydown", { key: "Escape" });
			await expect(page.locator(".es-menu[data-state='open']")).toHaveCount(0);
			await expect(trigger).toBeFocused();
		});

		test("renders a disabled option as a real disabled button, never a live row", async ({
			page,
		}) => {
			await explorer_group(page, "Groups, shortcuts and disabled rows")
				.locator('[aria-haspopup="menu"]')
				.first()
				.click();

			await expect(page.locator(".es-menu[data-state='open']")).toBeAttached();
			const archive = menu_item(page, "Archive");
			await expect(archive).toHaveJSProperty("tagName", "BUTTON");
			await expect(archive).toBeDisabled();
		});

		test("separates shortcut keys on Linux and Windows while keeping Mac symbols compact", async ({
			page,
		}) => {
			const trigger = explorer_group(page, "Groups, shortcuts and disabled rows")
				.locator('[aria-haspopup="menu"]')
				.first();
			const shortcut = menu_item(page, "Rename").locator(".es-menu__shortcut");

			await page.evaluate(() => {
				frappe.utils.is_mac = () => false;
			});
			await trigger.click();
			await expect(shortcut).toHaveText("Ctrl+R");

			await trigger.click();
			await page.evaluate(() => {
				frappe.utils.is_mac = () => true;
			});
			await trigger.click();
			await expect(shortcut).toHaveText("⌘R");
		});

		test("async options open in a loading state, then fill in when the promise settles", async ({
			page,
		}) => {
			const open_menu = page.locator(".es-menu[data-state='open']");

			await explorer_group(page, "Async items")
				.locator('[aria-haspopup="menu"]')
				.first()
				.click();

			await expect(open_menu).toHaveAttribute("aria-busy", "true");
			await expect(open_menu.locator(".es-menu__loading")).toBeAttached();
			await expect(page.locator(".es-menu__item")).toHaveCount(0);

			await expect(menu_item(page, "Fetched row 1")).toBeAttached();
			await expect(open_menu).not.toHaveAttribute("aria-busy");
			await expect(page.locator(".es-menu__loading")).toHaveCount(0);

			await menu_item(page, "Fetched row 2").click();
			await expect(open_menu).toHaveCount(0);
			await expect(
				page.locator(".es-toast", { hasText: containing("Row 2") }).first()
			).toBeAttached();
		});

		test("a function submenu loads on hover and swaps in its rows", async ({ page }) => {
			await explorer_group(page, "Async items")
				.locator('[aria-haspopup="menu"]')
				.nth(1)
				.click();

			await menu_item(page, "Recent documents").dispatchEvent("pointerenter");
			await expect(page.locator(".es-menu[data-state='open']")).toHaveCount(2);

			await expect(menu_item(page, "Doc A")).toBeAttached();
			await menu_item(page, "Doc A").click();
			await expect(page.locator(".es-menu[data-state='open']")).toHaveCount(0);
			await expect(
				page.locator(".es-toast", { hasText: containing("Doc A") }).first()
			).toBeAttached();
		});

		test("a rejected submenu shows the failure notice instead of a dead panel", async ({
			page,
		}) => {
			await explorer_group(page, "Async items")
				.locator('[aria-haspopup="menu"]')
				.nth(1)
				.click();

			await menu_item(page, "Fails to load").dispatchEvent("pointerenter");
			await expect(page.locator(".es-menu[data-state='open']")).toHaveCount(2);
			await expect(
				page
					.locator(".es-menu__empty", { hasText: containing("Couldn't load options") })
					.first()
			).toBeAttached();

			await page.locator(":focus").dispatchEvent("keydown", { key: "Escape" });
			await expect(page.locator(".es-menu[data-state='open']")).toHaveCount(0);
		});
	});

	test.describe("Toast — legacy HTML message sanitisation", () => {
		test("strips a javascript: href hidden behind an HTML-entity tab", async ({ page }) => {
			await page.evaluate(() => {
				frappe.show_alert({
					message: 'safe <a class="probe" href="java&#9;script:alert(1)">x</a>',
					indicator: "blue",
				});
			});

			await expect(page.locator(".es-toast .probe")).toBeAttached();
			await expect(page.locator(".es-toast .probe")).not.toHaveAttribute("href");
		});

		test("strips an on* handler attribute but keeps safe tags and hrefs", async ({ page }) => {
			await page.evaluate(() => {
				frappe.show_alert({
					message:
						'<strong class="ok-strong">Saved</strong> ' +
						'<a class="ok-link" href="/app/todo" onclick="alert(1)">open</a>',
					indicator: "green",
				});
			});

			await expect(page.locator(".es-toast .ok-strong")).toContainText("Saved");
			await expect(page.locator(".es-toast .ok-link")).toHaveAttribute("href", "/app/todo");
			await expect(page.locator(".es-toast .ok-link")).not.toHaveAttribute("onclick");
		});
	});

	test.describe("Context Menu", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Context Menu");
		});

		test("opens at the pointer, marks the target data-state=open, and Escape closes + clears it", async ({
			page,
		}) => {
			const surface = explorer_group(page, "Basic").locator(".explorer-preview > *").first();

			await surface.click({ button: "right" });
			await expect(page.locator(".es-menu[data-state='open']")).toBeFocused();
			await expect(surface).toHaveAttribute("data-state", "open");

			await page.locator(":focus").dispatchEvent("keydown", { key: "Escape" });
			await expect(page.locator(".es-menu[data-state='open']")).toHaveCount(0);
			await expect(surface).not.toHaveAttribute("data-state");
		});

		test("opens only the innermost menu when one target sits inside another's", async ({
			page,
		}) => {
			await page.evaluate(() => {
				const outer = document.createElement("div");
				outer.className = "nested-menu-outer";
				outer.style.cssText =
					"position: fixed; top: 200px; left: 400px; padding: 40px; z-index: 2000; background: white;";
				const inner = document.createElement("div");
				inner.className = "nested-menu-inner";
				inner.textContent = "Inner";
				outer.appendChild(inner);
				document.body.appendChild(outer);

				new frappe.ui.ContextMenu({
					target: outer,
					options: [{ label: "Outer action" }],
				});
				new frappe.ui.ContextMenu({
					target: inner,
					options: [{ label: "Inner action" }],
				});
			});
			const open_menu = page.locator(".es-menu[data-state='open']");
			const outer = page.locator(".nested-menu-outer");

			await page.locator(".nested-menu-inner").click({ button: "right" });
			await expect(open_menu).toHaveCount(1);
			await expect(open_menu).toContainText("Inner action");
			await expect(outer).not.toHaveAttribute("data-state");

			await outer.click({ button: "right", position: { x: 5, y: 5 } });
			await expect(open_menu).toHaveCount(1);
			await expect(open_menu).toContainText("Outer action");
		});
	});

	test.describe("Tooltip", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Tooltip");
		});

		test("shows on hover with role=tooltip + aria-describedby, then hides on leave", async ({
			page,
		}) => {
			const trigger = page
				.locator(".es-button", { hasText: containing("No delay") })
				.first();

			await trigger.dispatchEvent("pointerenter", { pointerType: "mouse" });
			await expect(page.locator(".es-tooltip[role='tooltip']")).toBeAttached();
			await expect(trigger).toHaveAttribute("aria-describedby");

			await trigger.dispatchEvent("pointerleave");
			await expect(page.locator(".es-tooltip")).toHaveCount(0);
			await expect(trigger).not.toHaveAttribute("aria-describedby");
		});

		test("drops the arrow for es-tooltip--plain, and keeps it otherwise", async ({ page }) => {
			const trigger = page
				.locator(".es-button", { hasText: containing("No delay") })
				.first();

			await trigger.dispatchEvent("pointerenter", { pointerType: "mouse" });
			await expect(page.locator(".es-tooltip")).not.toHaveClass(
				with_class("es-tooltip--plain")
			);
			await expect(page.locator(".es-tooltip .es-tooltip__arrow")).toBeAttached();
			await trigger.dispatchEvent("pointerleave");

			const tip = await page.evaluateHandle(() => {
				const tip = new frappe.ui.Tooltip(document.body, {
					text: "Plain",
					delay: 0,
					class: "es-tooltip--plain",
				});
				tip.show();
				return tip;
			});
			await expect(page.locator(".es-tooltip.es-tooltip--plain")).toBeAttached();
			await expect(page.locator(".es-tooltip .es-tooltip__arrow")).toHaveCount(0);
			await tip.evaluate((tip) => tip.destroy());
		});
	});

	test.describe("Popover", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Popover");
		});

		test("opens a dialog, moves focus into it, and Escape closes + returns focus to the trigger", async ({
			page,
		}) => {
			const trigger = explorer_group(page, "Interactive content")
				.locator('[aria-haspopup="dialog"]')
				.first();

			await trigger.click();
			await expect(
				page.locator(".es-popover[role='dialog'][data-state='open']")
			).toBeFocused();

			await page.locator(".es-popover").dispatchEvent("keydown", { key: "Escape" });
			await expect(page.locator(".es-popover[data-state='open']")).toHaveCount(0);
			await expect(trigger).toBeFocused();
		});
	});

	test.describe("Hover Card", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Hover Card");
		});

		test("opens on hover after the delay and closes on Escape", async ({ page }) => {
			await page
				.locator("a", { hasText: containing("Fast card") })
				.first()
				.dispatchEvent("pointerenter", { pointerType: "mouse" });
			await expect(page.locator(".es-hover-card")).toBeAttached();

			await page.locator("body").dispatchEvent("keydown", { key: "Escape" });
			await expect(page.locator(".es-hover-card")).toHaveCount(0);
		});
	});

	test.describe("Tabs", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Tabs");
		});

		test("switches the active panel on tab click, rendering lazy content", async ({
			page,
		}) => {
			const tabs = explorer_group(page, "Horizontal (arrows").locator(".es-tabs").first();
			const activity = tabs
				.locator(".es-tabs__tab", { hasText: containing("Activity") })
				.first();

			await activity.click();
			await expect(activity).toHaveAttribute("aria-selected", "true");
			await expect(tabs.locator(".es-tabs__panel[data-state='active']")).toContainText(
				"Rendered lazily"
			);
		});
	});

	test.describe("Tab Buttons", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Tab Buttons");
		});

		test("selects a pill on click (aria-checked) and unchecks the others", async ({
			page,
		}) => {
			const buttons = explorer_group(page, "Types").locator(".es-tab-buttons").first();
			const pill = (label) =>
				buttons.locator(".es-pill", { hasText: containing(label) }).first();

			await pill("In Progress").click();
			await expect(pill("In Progress")).toHaveAttribute("data-state", "active");
			await expect(pill("In Progress")).toHaveAttribute("aria-checked", "true");
			await expect(pill("Open")).toHaveAttribute("aria-checked", "false");
		});

		test("renders a disabled option as a disabled button", async ({ page }) => {
			const buttons = explorer_group(page, "Disabled options")
				.locator(".es-tab-buttons")
				.first();

			await expect(
				buttons.locator(".es-pill", { hasText: containing("2500") }).first()
			).toBeDisabled();
		});
	});

	test.describe("Progress", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Progress");
		});

		test("exposes the value through aria and the hint text", async ({ page }) => {
			const progress = explorer_group(page, "Basic (label").locator(".es-progress").first();

			await expect(
				progress.locator(".es-progress__track[role='progressbar']")
			).toHaveAttribute("aria-valuenow", "30");
			await expect(progress.locator(".es-progress__hint")).toContainText("30%");
		});

		test("fills the right number of interval segments for the value", async ({ page }) => {
			await expect(
				explorer_group(page, "Intervals")
					.locator(".es-progress__track[data-intervals]")
					.first()
					.locator(".es-progress__segment[data-filled]")
			).toHaveCount(3);
		});
	});
});
