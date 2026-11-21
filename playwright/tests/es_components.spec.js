import { test, expect } from "../support";

const escape_regex = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const containing = (text) => new RegExp(escape_regex(text));
const with_class = (name) => new RegExp(`(^|\\s)${escape_regex(name)}(\\s|$)`);

// a group's title shows only the part before " (", the rest moves into its code
const explorer_group = (page, title) =>
	page
		.locator(".explorer-group", {
			has: page.locator(".explorer-group__title", {
				hasText: new RegExp(`^${escape_regex(title.split(" (")[0])}`),
			}),
		})
		.first();
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
		await expect(page.locator(".explorer-grid")).toBeAttached();
	});

	test.describe("Grid", () => {
		test("search narrows the cards, and a card opens its component", async ({ page }) => {
			const cards = page.locator(".explorer-card:visible");
			await page.locator(".explorer-search").fill("combo");
			await expect(cards).toHaveCount(2);
			await expect(page.locator(".explorer-count")).toHaveText(/^2 of \d+ components$/);

			await page.locator(".explorer-search").fill("nothing like this");
			await expect(cards).toHaveCount(0);
			await expect(page.locator(".explorer-empty")).toContainText("No components match");
			await page.getByRole("button", { name: "Clear search" }).click();
			await expect(page.locator(".explorer-search")).toHaveValue("");
			await expect(cards).toHaveCount(await page.locator(".explorer-card").count());
			await expect(page.locator(".explorer-count")).toHaveText(/^\d+ components$/);

			await page.locator(".explorer-search").fill("button");
			await page.locator('.explorer-card[data-name="Button"]').click();
			await expect(page).toHaveURL(/\/component-explorer\/button$/);
			await expect(page.locator('.explorer-groups[data-component="Button"]')).toBeAttached();
		});

		test("a component still loading when the page is left keeps off the next page's title", async ({
			page,
		}) => {
			let release;
			const held = new Promise((resolve) => (release = resolve));
			await page.route(/desk_charts\.bundle/, async (route) => {
				await held;
				await route.continue();
			});
			await page.goto("/desk/component-explorer/stat-card", {
				waitUntil: "domcontentloaded",
			});
			await page.waitForFunction(() => frappe.pages["component-explorer"]?.render_component);
			await page.evaluate(() => frappe.set_route("List", "ToDo"));
			await expect(page).toHaveTitle(/To ?Do/);

			release();
			await page.waitForFunction(() => frappe.ui.stat_card);
			await page.evaluate(() => new Promise((resolve) => setTimeout(resolve, 100)));
			await expect(page).toHaveTitle(/To ?Do/);
		});
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

		test("a row's highlight clears when the pointer leaves it", async ({ page }) => {
			const trigger = explorer_group(page, "Basic actions")
				.locator('[aria-haspopup="menu"]')
				.first();
			await trigger.click();
			const row = page.locator(".es-menu[data-state='open'] .es-menu__item").first();

			await row.hover();
			await expect(row).toHaveAttribute("data-highlighted", "");
			const box = await page.locator(".es-menu[data-state='open']").boundingBox();
			await page.mouse.move(box.x + box.width + 40, box.y + box.height + 40);
			await expect(page.locator(".es-menu__item[data-highlighted]")).toHaveCount(0);

			const panel = page.locator(".es-menu[data-state='open']");
			await expect(panel).toBeFocused();
			await panel.press("ArrowDown");
			await expect(row).toHaveAttribute("data-highlighted", "");
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
			const surface = explorer_group(page, "Basic")
				.locator(".explorer-example__item > *")
				.first();

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

	test.describe("Bottom Sheet", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Bottom Sheet");
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
				"Edits and comments appear here"
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

	test.describe("List", () => {
		const applicants = (page) => explorer_group(page, "Rows");
		const row = (group, title) =>
			group.locator(".es-list__row", { hasText: containing(title) }).first();
		const use_list = (group, change) =>
			group.locator(".es-list").evaluate((el, change) => {
				const list = $(el).data("es-list");
				return new Function("list", change)(list);
			}, change);

		test.beforeEach(async ({ page }) => {
			await show(page, "List");
		});

		test("rows with an href are links, so cmd-click and middle-click work", async ({
			page,
		}) => {
			const rows = applicants(page).locator(".es-list__row");

			await expect(rows).toHaveCount(3);
			await expect(rows.first()).toHaveJSProperty("tagName", "A");
			await expect(rows.first()).toHaveAttribute("href", "/desk/job-applicant/jane");
		});

		test("a title with markup renders as text", async ({ page }) => {
			const group = applicants(page);

			await use_list(group, 'list.update_item("wade", { title: "<b>Wade</b> Warren" })');
			await expect(row(group, "Warren").locator(".es-list__title")).toHaveText(
				"<b>Wade</b> Warren"
			);
			await expect(group.locator(".es-list b")).toHaveCount(0);
		});

		test("update_item changes one row and keeps the others", async ({ page }) => {
			const group = applicants(page);

			await use_list(
				group,
				'list.update_item("wade", { subtitle: "wade@acme.com", meta: "1h ago" })'
			);
			await expect(row(group, "Wade Warren").locator(".es-list__subtitle")).toHaveText(
				"wade@acme.com"
			);
			await expect(row(group, "Wade Warren").locator(".es-list__meta")).toHaveText("1h ago");
			await expect(group.locator(".es-list__row")).toHaveCount(3);
		});

		test("remove_item drops the row", async ({ page }) => {
			const group = applicants(page);

			await use_list(group, 'list.remove_item("wade")');
			await expect(group.locator(".es-list__row")).toHaveCount(2);
			await expect(row(group, "Wade Warren")).toHaveCount(0);
		});

		test("max folds the list until Show all, and set_items keeps it open", async ({
			page,
		}) => {
			const group = explorer_group(page, "Folds after max");
			const rows = group.locator(".es-list__row");
			const more = group.locator(".es-list__more");

			await expect(rows).toHaveCount(3);
			await expect(more).toHaveText("Show all 7");

			await more.click();
			await expect(rows).toHaveCount(7);
			await expect(more).toHaveCount(0);

			await use_list(group, "list.set_items(list.get_items().slice(0, 5))");
			await expect(rows).toHaveCount(5);
		});

		test("no items shows the empty state instead of the box", async ({ page }) => {
			const list = explorer_group(page, "Empty (shows").locator(".es-list");

			await expect(list).toHaveAttribute("data-empty", "");
			await expect(list.getByText("No new applicants")).toBeVisible();
			await expect(list.locator(".es-list__row")).toHaveCount(0);
		});

		test("selected marks one row, follows set_selected and survives a re-render", async ({
			page,
		}) => {
			const group = explorer_group(page, "Selected row");
			const selected = group.locator(".es-list__row[data-selected]");

			await expect(selected).toHaveCount(1);
			await expect(selected).toContainText("Wade Warren");
			await expect(selected).toHaveAttribute("aria-current", "true");

			await row(group, "Jane Cooper").click();
			await expect(selected).toContainText("Jane Cooper");
			await expect(group.locator("[aria-current]")).toHaveCount(1);

			await use_list(group, "list.set_items(list.get_items().slice())");
			await expect(selected).toContainText("Jane Cooper");

			await use_list(group, 'list.remove_item("jane")');
			await expect(selected).toHaveCount(0);
			expect(await use_list(group, "return list.get_selected()")).toBeNull();

			await use_list(group, 'list.set_selected("esther")');
			await expect(selected).toContainText("Esther Howard");
			await use_list(group, "list.set_selected(null)");
			await expect(selected).toHaveCount(0);
		});

		test("flat variant drops the box", async ({ page }) => {
			const flat = explorer_group(page, "Flat variant").locator(".es-list");
			await expect(flat).toHaveAttribute("data-variant", "flat");
			await expect(flat).toHaveCSS("border-top-width", "0px");
			await expect(flat.locator(".es-list__row")).toHaveCount(3);
		});

		test("an action click does not open the row", async ({ page }) => {
			const group = applicants(page);
			const jane = row(group, "Jane Cooper");
			const opened = page.locator(".es-toast", { hasText: containing("Opened") });

			await jane.hover();
			await jane.getByRole("button", { name: "Shortlist" }).click();
			await expect(jane.locator(".es-badge")).toHaveText("Shortlisted");
			await expect(opened).toHaveCount(0);

			await jane.locator(".es-list__title").click();
			await expect(opened.first()).toContainText("Opened Jane Cooper");
		});

		test("a second click on a busy action does not open the row", async ({ page }) => {
			const group = applicants(page);
			const jane = row(group, "Jane Cooper");
			const hold = jane.locator(".es-list__actions .es-button");
			const opened = page.locator(".es-toast", { hasText: containing("Opened") });

			await use_list(
				group,
				'list.update_item("jane", { actions: [{ label: "Hold", onclick: () => new Promise(() => {}) }] })'
			);
			await jane.hover();
			await hold.click();
			await expect(hold).toHaveAttribute("aria-busy", "true");
			// a busy button ignores pointer events, so this click lands on the actions around it
			await hold.click({ force: true });
			await expect(opened).toHaveCount(0);
		});

		test("controls show without hover", async ({ page }) => {
			const group = explorer_group(page, "Controls");

			await page.mouse.move(0, 0);
			await expect(group.locator(".es-list__controls")).toHaveCount(3);
			await expect(
				row(group, "Wade Warren").getByRole("button", { name: "Applied" })
			).toBeVisible();
		});

		test("a control click in a link row neither opens the row nor follows the link", async ({
			page,
		}) => {
			const group = explorer_group(page, "Controls");
			const jane = row(group, "Jane Cooper");
			const opened = page.locator(".es-toast", { hasText: containing("Opened") });
			const url = page.url();

			await expect(jane).toHaveJSProperty("tagName", "A");
			await jane.getByRole("button", { name: "Applied" }).click();
			await menu_item(page, "Shortlisted").click();
			await expect(jane.getByRole("button", { name: "Shortlisted" })).toBeVisible();
			await expect(opened).toHaveCount(0);
			expect(page.url()).toBe(url);

			await jane.locator(".es-list__title").click();
			await expect(opened.first()).toContainText("Opened Jane Cooper");
		});

		test("groups show a heading and count, with their rows under them", async ({ page }) => {
			const list = explorer_group(page, "Grouped rows").locator(".es-list");
			const heads = list.locator(".es-list__group-head");
			const rows_under = (head) =>
				head.locator("xpath=following-sibling::*[1]").locator(".es-list__row");

			await expect(list).toHaveAttribute("data-grouped", "");
			await expect(heads).toHaveCount(2);
			await expect(heads.locator(".es-list__group-label")).toHaveText([
				"Feedback due",
				"Cleared",
			]);
			await expect(heads.locator(".es-list__group-count")).toHaveText(["2", "1"]);
			await expect(rows_under(heads.nth(0))).toHaveText([/Jane Cooper/, /Wade Warren/]);
			await expect(rows_under(heads.nth(1))).toHaveText([/Esther Howard/]);
		});
	});

	test.describe("Rating", () => {
		test.beforeEach(async ({ page }) => {
			await show(page, "Rating");
		});

		test("rounds the value to the step and names it for screen readers", async ({ page }) => {
			const whole = explorer_group(page, "Values").locator(".es-rating").nth(2);
			await expect(whole).toHaveAttribute("aria-label", "4 out of 5");
			await expect(whole.locator('.es-rating__half[data-state="filled"]')).toHaveCount(8);

			const half = explorer_group(page, "Half steps").locator(".es-rating").first();
			await expect(half).toHaveAttribute("aria-label", "3.5 out of 5");
			await expect(half.locator('.es-rating__half[data-state="filled"]')).toHaveCount(7);
		});
	});
});
