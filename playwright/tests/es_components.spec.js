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

	test.describe("Stat Card", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Stat Card");
		});

		const stat_card = (group, label) =>
			group.locator(".es-stat-card", { hasText: containing(label) }).first();

		test("tones the delta by positive_is_good, so a rise in a bad metric reads red", async ({
			page,
		}) => {
			const group = explorer_group(page, "Trend delta");
			const net_sales = stat_card(group, "Net sales").locator(".es-stat-card__delta");

			await expect(net_sales).toHaveAttribute("data-tone", "positive");
			await expect(net_sales).toContainText("+12.4%");
			await expect(
				stat_card(group, "Overdue").locator(".es-stat-card__delta")
			).toHaveAttribute("data-tone", "negative");
			await expect(
				stat_card(group, "Returns").locator(".es-stat-card__delta")
			).toHaveAttribute("data-tone", "neutral");
		});

		test("preserves the direction of changes below display precision", async ({ page }) => {
			const cases = [
				[0.01, "+", "positive"],
				[-0.01, "−", "negative"],
			];
			const deltas = await page.evaluate(
				(values) =>
					values.map((value) => {
						const delta = frappe.ui
							.stat_card({ label: "Small change", value: 1, delta: { value } })
							.find(".es-stat-card__delta");
						return { text: delta.text(), tone: delta.attr("data-tone") };
					}),
				cases.map(([value]) => value)
			);

			cases.forEach(([, sign, tone], i) => {
				expect(deltas[i].text).toContain(`${sign}<0.1%`);
				expect(deltas[i].tone).toBe(tone);
			});
		});

		test("shows a dash and No data for a missing reading, but prints a zero", async ({
			page,
		}) => {
			const group = explorer_group(page, "No reading");
			const conversion_rate = stat_card(group, "Conversion rate");
			const refunds = stat_card(group, "Refunds");

			await expect(conversion_rate).toHaveAttribute("data-state", "empty");
			await expect(conversion_rate).toContainText("—");
			await expect(conversion_rate).toContainText("No data");
			await expect(refunds).not.toHaveAttribute("data-state");
			await expect(refunds.locator(".es-stat-card__value")).toHaveText("0");
		});

		test("holds the card's shape with skeletons while loading", async ({ page }) => {
			const card = explorer_group(page, "Loading").locator(
				".es-stat-card[data-state='loading']"
			);

			await expect(card).toHaveAttribute("aria-busy", "true");
			await expect(card.locator(".es-stat-card__label")).toHaveText("Net sales");
			await expect(card.locator(".es-skeleton")).toHaveCount(2);
		});

		test("makes a clickable card a keyboard button", async ({ page }) => {
			const card = explorer_group(page, "Series dot").locator(".es-stat-card--clickable");

			await expect(card).toHaveAttribute("role", "button");
			await expect(card).toHaveAttribute("tabindex", "0");
			await card.dispatchEvent("keydown", { key: "Enter" });
			await expect(page.locator(".es-toast")).toContainText("Paid");
		});
	});

	test.describe("Bar List", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Bar List");
		});

		test("sizes bars against a rounded axis and labels every row", async ({ page }) => {
			const group = explorer_group(page, "Basic");

			await expect(group.locator(".es-bar-list__row")).toHaveCount(4);
			await expect(group.locator(".es-bar-list__bar").first()).toHaveAttribute(
				"style",
				/width: 84%/
			);
			await expect(group.locator(".es-bar-list__tick").last()).toHaveText("50000");
		});

		test("keeps static values visible and expands an undersized axis", async ({ page }) => {
			const chart = await page.evaluate(() => {
				const chart = frappe.ui
					.bar_list({
						items: [{ label: "Total", value: 200 }],
						max: 100,
						values_on_hover: true,
					})
					.appendTo(document.body);
				const result = {
					value_opacity: getComputedStyle(chart.find(".es-bar-list__value")[0]).opacity,
					row_role: chart.find(".es-bar-list__row").attr("role") ?? null,
					bar_width: parseFloat(chart.find(".es-bar-list__bar")[0].style.width),
					last_tick: Number(chart.find(".es-bar-list__tick").last().text()),
				};
				chart.remove();
				return result;
			});

			expect(chart.value_opacity).toBe("1");
			expect(chart.row_role).toBeNull();
			expect(chart.bar_width).toBeLessThanOrEqual(100);
			expect(chart.last_tick).toBeGreaterThanOrEqual(200);
		});

		test("says there is no data instead of drawing an empty axis", async ({ page }) => {
			const chart = explorer_group(page, "Empty").locator(
				".es-bar-list[data-state='empty']"
			);

			await expect(chart.locator(".es-bar-list__empty")).toHaveText("No data to show");
			await expect(chart.locator(".es-bar-list__axis")).toHaveCount(0);
		});

		test("widens the label gutter and passes the clicked item back", async ({ page }) => {
			const group = explorer_group(page, "Wide labels");

			await expect(group.locator(".es-bar-list").first()).toHaveAttribute("style", /180px/);
			await group.locator(".es-bar-list__row--clickable").first().click();
			await expect(page.locator(".es-toast")).toContainText("Kaveri Industrial Supplies");
		});
	});

	test.describe("Donut", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Donut");
		});

		const legend_row = (group, label) =>
			group.locator(".es-donut__legend-row", { hasText: containing(label) }).first();

		test("draws one segment per value and labels the chart for screen readers", async ({
			page,
		}) => {
			const group = explorer_group(page, "Centre value");

			await expect(group.locator(".es-donut__seg")).toHaveCount(3);
			await expect(group.locator(".es-donut__svg")).toHaveAttribute(
				"aria-label",
				"Paid: 70 (70%), Unpaid: 20 (20%), Overdue: 10 (10%)"
			);
			await expect(group.locator(".es-donut__value")).toHaveText("70%");
		});

		test("swaps the centre to a hovered legend row and restores it on leave", async ({
			page,
		}) => {
			const group = explorer_group(page, "Centre value");
			const unpaid = legend_row(group, "Unpaid");

			await unpaid.hover();
			await expect(unpaid).toHaveClass(with_class("is-active"));
			await expect(group.locator(".es-donut__label")).toHaveText("Unpaid · 20%");
			await expect(group.locator(".es-donut__seg.is-dim")).toHaveCount(2);

			await group.locator(".es-donut__legend").dispatchEvent("mouseout");
			await expect(group.locator(".es-donut__value")).toHaveText("70%");
			await expect(group.locator(".es-donut__seg.is-dim")).toHaveCount(0);
		});

		test("clears the tooltip and highlight when leaving a segment for the centre", async ({
			page,
		}) => {
			const group = explorer_group(page, "Centre value");
			const segment = group.locator(".es-donut__seg").first();

			await segment.dispatchEvent("mouseover", { clientX: 100, clientY: 100 });
			await expect(group.locator(".es-donut__tip")).toHaveClass(with_class("is-visible"));
			await segment.dispatchEvent("mouseout");
			await expect(group.locator(".es-donut__tip")).not.toHaveClass(
				with_class("is-visible")
			);
			await expect(group.locator(".es-donut__seg.is-dim")).toHaveCount(0);
			await expect(group.locator(".es-donut__value")).toHaveText("70%");
		});

		test("exposes amounts without hover and highlights a keyboard-focused legend", async ({
			page,
		}) => {
			const group = explorer_group(page, "Centre value");
			const unpaid = legend_row(group, "Unpaid");

			await expect(unpaid).toContainText("20 · 20%");
			await unpaid.focus();
			await expect(unpaid).toHaveClass(with_class("is-active"));
			await expect(group.locator(".es-donut__value")).toHaveText("20");
			await group.locator(".es-donut__legend-row:focus").blur();
			await expect(group.locator(".es-donut__value")).toHaveText("70%");
		});

		test("says there is no data in the ring's place when there is nothing to chart", async ({
			page,
		}) => {
			const chart = explorer_group(page, "Empty").locator(".es-donut[data-state='empty']");

			await expect(chart.locator(".es-donut__empty")).toHaveText("No data to show");
			await expect(chart.locator(".es-donut__svg")).toHaveCount(0);
			await expect(chart.locator(".es-donut__legend")).toHaveCount(0);
		});
	});
});
