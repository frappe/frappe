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

	test.describe("BottomSheet", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "BottomSheet");
		});

		test("opens as a dialog with focus inside, and Escape closes it back to the trigger", async ({
			page,
		}) => {
			const trigger = explorer_group(page, "Picker (the current choice is checked")
				.locator('[aria-haspopup="dialog"]')
				.first();

			await trigger.click();
			await expect(page.locator(".es-bottom-sheet[role='dialog']")).toBeFocused();

			await page.locator(".es-bottom-sheet").dispatchEvent("keydown", { key: "Escape" });
			await expect(page.locator(".es-bottom-sheet-root[data-state='open']")).toHaveCount(0);
			await expect(trigger).toBeFocused();
		});

		test("search narrows the rows, a pick pushes a step and Back returns", async ({
			page,
		}) => {
			await explorer_group(page, "Steps inside one sheet")
				.locator('[aria-haspopup="dialog"]')
				.first()
				.click();

			await page.locator(".es-bottom-sheet__subheader input").fill("deliv");
			const rows = page.locator(".es-bottom-sheet__option:visible");
			await expect(rows).toHaveCount(1);
			await expect(rows).toContainText("Delivery Date");
			await rows.click();

			await expect(page.locator(".es-bottom-sheet__title")).toHaveText("Condition");
			await expect(page.locator(".es-bottom-sheet__subtitle")).toHaveText("Delivery Date");

			await page.locator(".es-bottom-sheet__back").click();
			await expect(page.locator(".es-bottom-sheet__title")).toHaveText("Choose field");
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

	test.describe("Optional Sections", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Optional Sections");
		});

		const add_button = (root, title) =>
			root
				.locator(".es-optional-sections__buttons .es-button", {
					hasText: containing(title),
				})
				.first();
		const section = (root, title) =>
			root.locator(".es-optional-sections__section", { hasText: containing(title) }).first();

		test("adding a section shows it and hides its button; Remove brings the button back", async ({
			page,
		}) => {
			const root = explorer_group(page, "Basic (add")
				.locator(".es-optional-sections")
				.first();

			await expect(section(root, "Salary and bank")).toBeHidden();
			await add_button(root, "Salary and bank").click();
			await expect(section(root, "Salary and bank")).toHaveAttribute("data-state", "added");
			await expect(section(root, "Salary and bank")).toContainText("Salary fields go here.");
			await expect(add_button(root, "Salary and bank")).toBeHidden();

			await section(root, "Salary and bank").getByRole("button", { name: "Remove" }).click();
			await expect(section(root, "Salary and bank")).toBeHidden();
			await expect(add_button(root, "Salary and bank")).toBeVisible();
			await expect(add_button(root, "Salary and bank")).toBeFocused();
		});

		test("hides the add row once every section is added", async ({ page }) => {
			const root = explorer_group(page, "A section added from the start")
				.locator(".es-optional-sections")
				.first();

			await expect(section(root, "Notes")).toBeVisible();
			await expect(add_button(root, "Notes")).toBeHidden();
			await add_button(root, "Attachments").click();
			await expect(root.locator(".es-optional-sections__more")).toBeHidden();
		});

		test("focuses the first input of an added section and lets on_remove reset it", async ({
			page,
		}) => {
			const root = explorer_group(page, "Fields in a section")
				.locator(".es-optional-sections")
				.first();
			const email = root.locator("input[data-fieldname='email']");

			await add_button(root, "Contact").click();
			await expect(email).toBeFocused();
			await email.fill("jane@example.com");
			await section(root, "Contact").getByRole("button", { name: "Remove" }).click();
			await add_button(root, "Contact").click();
			await expect(email).toHaveValue("");
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

	test.describe("Stepper", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Stepper");
		});

		test("vertical puts each step's content beside a line down to the next step", async ({
			page,
		}) => {
			const items = explorer_group(page, "Vertical").locator(".es-stepper__item");
			await expect(items).toHaveCount(3);

			// a line after every step but the last, marked done after a done step
			await expect(
				explorer_group(page, "Vertical").locator(".es-stepper__connector")
			).toHaveCount(2);
			await expect(items.nth(0).locator(".es-stepper__connector")).toHaveAttribute(
				"data-completed",
				"true"
			);

			await expect(items.nth(1).locator(".es-stepper__step")).toHaveAttribute(
				"aria-current",
				"step"
			);
			await expect(items.nth(1).locator(".es-stepper__content")).toContainText(
				"Bring the closing balances"
			);
			// a step without content gets no content box
			await expect(items.nth(2).locator(".es-stepper__content")).toHaveCount(0);
		});

		test("vertical content: a string stays text, and reused content keeps its value and focus", async ({
			page,
		}) => {
			const result = await page.evaluate(() => {
				const input = $(`<input>`);
				const $stepper = frappe.ui
					.stepper({
						orientation: "vertical",
						steps: [
							{ label: "One", content: "<b>not markup</b>" },
							{ label: "Two", content: () => input },
							{ label: "Three", content: () => $() },
						],
					})
					.appendTo("body");
				const stepper = $stepper.data("es-stepper");
				input.val("typed");
				input[0].focus();
				stepper.refresh();
				const kept_on_refresh = document.activeElement === input[0];
				// a step change rebuilds every step
				stepper.set_current(1);
				const out = {
					text: $stepper.find(".es-stepper__content").first().text(),
					bold: $stepper.find(".es-stepper__content b").length,
					value: $stepper.find("input").val(),
					focus: kept_on_refresh && document.activeElement === input[0],
					current: $stepper.find("[aria-current=step] .es-stepper__label").text(),
					boxes: $stepper.find(".es-stepper__content").length,
					items: $stepper.find("ol > li.es-stepper__item").length,
				};
				$stepper.remove();
				return out;
			});
			expect(result).toEqual({
				text: "<b>not markup</b>",
				bold: 0,
				value: "typed",
				focus: true,
				current: "Two",
				// the empty jQuery content gets no box
				boxes: 2,
				items: 3,
			});
		});

		test("a step is a button only when something handles its click", async ({ page }) => {
			await expect(
				explorer_group(page, "Click to navigate").locator("button.es-stepper__step")
			).toHaveCount(3);
			// nothing handles clicks here, so no dead tab stops
			await expect(
				explorer_group(page, "Vertical").locator(".es-stepper__step")
			).toHaveCount(3);
			await expect(
				explorer_group(page, "Vertical").locator("button.es-stepper__step")
			).toHaveCount(0);
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

	test.describe("DatePicker", () => {
		const input = (page, title) =>
			explorer_group(page, title).locator(".es-date-picker input").first();
		const panel = (page) => page.locator(".es-date-picker-panel");

		test.beforeEach(async ({ page }) => {
			await show(page, "DatePicker");
		});

		test("opens a six-week month with today selected", async ({ page }) => {
			await input(page, "Basic").click();
			await expect(panel(page).getByRole("gridcell")).toHaveCount(42);
			await expect(panel(page).locator("[data-selected]")).toHaveCount(1);
			await expect(input(page, "Basic")).toBeFocused();
		});

		test("the arrows move through the grid and Enter picks the date", async ({ page }) => {
			const field = input(page, "Basic");
			await field.click();
			await page.keyboard.press("ArrowDown");
			await expect(page.locator(".es-date-picker-calendar__day:focus")).toHaveAttribute(
				"data-selected",
				""
			);
			await page.keyboard.press("ArrowRight");
			await page.keyboard.press("Enter");
			await expect(panel(page)).toHaveCount(0);
			await expect(field).toBeFocused();
			await expect(field).not.toHaveValue("");
		});

		test("text that isn't a date goes back to the last value", async ({ page }) => {
			const field = input(page, "Basic");
			const before = await field.inputValue();
			await field.fill("not a date");
			await field.press("Enter");
			await expect(field).toHaveValue(before);
		});

		test("the title switches to months and years", async ({ page }) => {
			await input(page, "Basic").click();
			await panel(page).locator(".es-date-picker-calendar__title").click();
			await expect(panel(page).getByRole("listbox")).toHaveCount(2);
			await panel(page).getByRole("option", { name: "Jan", exact: true }).click();
			await expect(panel(page).getByRole("grid")).toBeVisible();
			await expect(panel(page).locator(".es-date-picker-calendar__title")).toContainText(
				/Jan/
			);
		});

		test("dates past the limits and blocked days can't be picked", async ({ page }) => {
			await input(page, "Limits and blocked days").click();
			const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
			const cell = panel(page).locator(`[data-value="${yesterday}"]`);
			if (await cell.count()) await expect(cell).toBeDisabled();
			await expect(
				panel(page).locator(".es-date-picker-calendar__day:disabled").first()
			).toBeVisible();
		});

		test("a shortcut sets the date and closes the calendar", async ({ page }) => {
			const field = input(page, "Shortcuts beside the calendar");
			await field.click();
			await panel(page).getByRole("button", { name: "Tomorrow" }).click();
			await expect(panel(page)).toHaveCount(0);
			await expect(field).not.toHaveValue("");
		});

		test("a trigger of your own opens the grid and gets focus back on Escape", async ({
			page,
		}) => {
			const trigger = explorer_group(page, "A trigger of your own").getByRole("button", {
				name: "Add due date",
			});
			await trigger.click();
			await expect(page.locator(".es-date-picker-calendar__day:focus")).toHaveCount(1);
			await page.keyboard.press("Escape");
			await expect(panel(page)).toHaveCount(0);
			await expect(trigger).toBeFocused();
		});
	});

	test.describe("Checklist", () => {
		const onboarding = (page) => explorer_group(page, "employee onboarding");
		const row = (group, label) =>
			group.locator(".es-checklist__item", { hasText: containing(label) }).first();
		const toggle = (row) => row.locator(".es-checklist__toggle");
		const count = (group) => group.locator(".es-checklist__count").first();

		test.beforeEach(async ({ page }) => {
			await show(page, "Checklist");
		});

		test("the first unfinished row opens first, and one row is open at a time", async ({
			page,
		}) => {
			const group = onboarding(page);
			const letter = row(group, "Appointment Letter");
			const employee = row(group, "Create Employee");

			await expect(toggle(letter)).toHaveAttribute("aria-expanded", "true");
			await expect(toggle(employee)).toHaveAttribute("aria-expanded", "false");

			await toggle(employee).click();
			await expect(employee).toHaveAttribute("data-open", "");
			await expect(letter).not.toHaveAttribute("data-open", "");
		});

		test("an action that finishes the open row checks it and opens the next", async ({
			page,
		}) => {
			const group = onboarding(page);
			await expect(count(group)).toHaveText("1 of 7 done");

			await row(group, "Appointment Letter").getByRole("button", { name: "Send" }).click();
			await expect(row(group, "Appointment Letter")).toHaveAttribute("data-status", "done");
			await expect(count(group)).toHaveText("2 of 7 done");
			await expect(row(group, "Create Employee")).toHaveAttribute("data-open", "");
		});

		test("a locked row says why and disables its actions until the caller unlocks it", async ({
			page,
		}) => {
			const group = onboarding(page);
			const holiday_list = row(group, "Assign Holiday List");

			await expect(holiday_list).toHaveAttribute("data-locked", "");
			await expect(holiday_list.locator(".es-checklist__lock")).toHaveAttribute(
				"aria-label",
				"Needs: Create Employee"
			);
			await expect(holiday_list.locator(".es-checklist__meta")).toHaveText("India 2026");
			await toggle(holiday_list).click();
			await expect(holiday_list.getByRole("button", { name: "Assign" })).toBeDisabled();

			await toggle(row(group, "Create Employee")).click();
			await row(group, "Create Employee").getByRole("button", { name: "Create" }).click();
			await expect(holiday_list).not.toHaveAttribute("data-locked", "");
			await expect(holiday_list).toHaveAttribute("data-open", "");
			await expect(holiday_list.getByRole("button", { name: "Assign" })).toBeEnabled();
		});

		test("a skipped row offers no action, so skipping can't unlock it", async ({ page }) => {
			const holiday_list = row(onboarding(page), "Assign Holiday List");

			await toggle(holiday_list).click();
			await holiday_list.getByRole("button", { name: "Skip" }).click();
			await expect(holiday_list).toHaveAttribute("data-status", "skipped");
			await expect(holiday_list.locator(".es-checklist__status")).toHaveText("Skipped");

			await toggle(holiday_list).click();
			await expect(holiday_list.getByRole("button", { name: "Assign" })).toHaveCount(0);
			await expect(holiday_list.getByRole("button", { name: "Undo skip" })).toBeVisible();
		});

		test("a past due date is overdue only while the row is unfinished", async ({ page }) => {
			const group = onboarding(page);

			await expect(row(group, "Appointment Letter")).toHaveAttribute("data-overdue", "");
			await expect(row(group, "Create User")).not.toHaveAttribute("data-overdue", "");
		});

		test("skipping the open row fills the bar, and the skip can be undone", async ({
			page,
		}) => {
			const group = explorer_group(page, "Basic");
			const invite = row(group, "Invite users");

			await expect(invite).toHaveAttribute("data-open", "");
			await invite.getByRole("button", { name: "Skip" }).click();
			await expect(invite).toHaveAttribute("data-status", "skipped");
			await expect(count(group)).toHaveText("1 of 2 done, 1 skipped");

			await toggle(invite).click();
			await invite.getByRole("button", { name: "Undo skip" }).click();
			await expect(invite).toHaveAttribute("data-status", "pending");
			await expect(count(group)).toHaveText("1 of 2 done");
		});

		test("a row with nothing to show doesn't open", async ({ page }) => {
			const company = row(explorer_group(page, "Basic"), "Create company");

			await toggle(company).click();
			await expect(company).toHaveAttribute("data-empty", "");
			await expect(company).not.toHaveAttribute("data-open", "");
		});

		test("owners and due dates are editable only when the caller can save them", async ({
			page,
		}) => {
			const editable = row(onboarding(page), "Create Employee");
			const read_only = row(explorer_group(page, "Read-only owners"), "Create Employee");

			await expect(editable.locator(".es-checklist__owner button")).toHaveCount(1);
			await expect(editable.locator(".es-checklist__due button")).toHaveCount(1);
			await expect(read_only.locator(".es-checklist__owner button")).toHaveCount(0);
			await expect(read_only.locator(".es-checklist__due button")).toHaveCount(0);
		});

		test("the owner opens a user combobox and the date opens a date picker", async ({
			page,
		}) => {
			const employee = row(onboarding(page), "Create Employee");

			await expect(employee.locator(".es-checklist__owner [role=combobox]")).toContainText(
				"Select assignee"
			);
			await employee.locator(".es-checklist__owner [role=combobox]").click();
			const users = page.locator(".es-combobox__panel");
			await expect(users.locator(".es-combobox__search input")).toBeFocused();
			await page.keyboard.type("administrator");
			await expect(users.getByRole("option", { name: /Administrator/ })).toBeVisible();
			await page.keyboard.press("Enter");
			await expect(users).toHaveCount(0);

			await employee.locator(".es-checklist__due button").click();
			const calendar = page.locator(".es-date-picker-panel");
			await expect(calendar.getByRole("grid")).toBeVisible();
			await page.keyboard.press("ArrowRight");
			await page.keyboard.press("Enter");
			await expect(calendar).toHaveCount(0);
		});

		test("the marker sets an unfinished row In Progress or Stuck, shown as a badge", async ({
			page,
		}) => {
			const group = onboarding(page);
			const employee = row(group, "Create Employee");

			await expect(employee.locator(".es-checklist__status")).toHaveText("");
			await employee.locator(".es-checklist__marker button").click();
			await page.locator(".es-menu__item", { hasText: "Stuck" }).click();
			await expect(employee).toHaveAttribute("data-status", "stuck");
			await expect(employee.locator(".es-checklist__status")).toHaveText("Stuck");
			await expect(employee).not.toHaveAttribute("data-open", "");

			const user = row(group, "Create User");
			await expect(user.locator(".es-checklist__status")).toHaveText("");
			await expect(user.locator(".es-checklist__marker button")).toHaveCount(0);
		});

		test("a card folds its items away but keeps its head and progress", async ({ page }) => {
			const card = onboarding(page).locator(".es-checklist").first();
			const head = card.locator(".es-checklist__head");

			await expect(head).toHaveAttribute("aria-expanded", "true");
			await head.click();
			await expect(head).toHaveAttribute("aria-expanded", "false");
			await expect(card.locator(".es-progress")).toBeVisible();
			await expect(card.locator(".es-checklist__items")).not.toBeInViewport();
		});

		test("typing a label and pressing Enter adds an item, and Remove deletes it", async ({
			page,
		}) => {
			const group = explorer_group(page, "adding and removing");
			const input = group.getByRole("textbox", { name: "Add activity" });

			await input.fill("Order a desk");
			await input.press("Enter");
			await expect(row(group, "Order a desk")).toBeVisible();
			await expect(input).toHaveValue("");
			await expect(input).toBeFocused();

			await toggle(row(group, "Order a desk")).click();
			await row(group, "Order a desk").getByRole("button", { name: "Remove" }).click();
			await expect(
				group.locator(".es-checklist__item", { hasText: "Order a desk" })
			).toHaveCount(0);
		});

		test("leaving the add input with text in it adds the item", async ({ page }) => {
			const group = explorer_group(page, "adding and removing");
			const input = group.getByRole("textbox", { name: "Add activity" });

			await input.fill("Order a chair");
			await input.blur();
			await expect(row(group, "Order a chair")).toBeVisible();
			await expect(input).toHaveValue("");
			await expect(input).not.toBeFocused();
		});

		test("Escape clears the add input without adding an item", async ({ page }) => {
			const group = explorer_group(page, "adding and removing");
			const input = group.getByRole("textbox", { name: "Add activity" });

			await input.fill("Not this one");
			await input.press("Escape");
			await expect(input).toHaveValue("");
			await expect(group.locator(".es-checklist__item")).toHaveCount(1);
		});
	});
});
