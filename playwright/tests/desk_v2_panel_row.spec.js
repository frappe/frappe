import { test, expect } from "../support";

const DOCTYPE = "Panel Row Box 46991";
const SLUG = "panel-row-box-46991";

const TYPES = [
	{ fieldname: "f_data", fieldtype: "Data", label: "Data Field" },
	{ fieldname: "f_url", fieldtype: "Data", options: "URL", label: "URL Field" },
	{ fieldname: "f_email", fieldtype: "Data", options: "Email", label: "Email Field" },
	{ fieldname: "f_int", fieldtype: "Int", label: "Int Field" },
	{ fieldname: "f_float", fieldtype: "Float", label: "Float Field" },
	{ fieldname: "f_currency", fieldtype: "Currency", label: "Currency Field" },
	{ fieldname: "f_percent", fieldtype: "Percent", label: "Percent Field" },
	{ fieldname: "f_phone", fieldtype: "Phone", label: "Phone Field" },
	{ fieldname: "f_duration", fieldtype: "Duration", label: "Duration Field" },
	{ fieldname: "f_password", fieldtype: "Password", label: "Password Field" },
	{ fieldname: "f_email_long", fieldtype: "Data", options: "Email", label: "Long Email" },
	{ fieldname: "f_ph", fieldtype: "Data", label: "Nickname", placeholder: "Enter a nickname" },
];
const VALUES = {
	f_data: "hello",
	f_url: "https://example.com",
	f_email: "a@example.com",
	f_int: 5,
	f_float: 2.5,
	f_currency: 100,
	f_percent: 12,
	f_phone: "+911234567890",
	f_duration: 5400,
	f_password: "secret",
	f_email_long:
		"a.very.long.email.address.for.the.panel.row.box@a-rather-long-subdomain.example-company.com",
};
const LAYOUT = [
	{
		name: "tab_1",
		sections: [
			{
				name: "types",
				label: "Types",
				columns: [{ name: "column_1", fields: TYPES.map((t) => t.fieldname) }],
			},
		],
	},
];

const row = (page, fieldname) => page.locator(`.field-box [data-fieldname="${fieldname}"]`);

// The geometry of one panel row in its current state, read in the page.
function measure(fieldname) {
	const cell = document.querySelector(`.field-box [data-fieldname="${fieldname}"]`);
	const box = cell.closest(".field-box");
	const rect = box.getBoundingClientRect();
	const column = box.parentElement.getBoundingClientRect();
	const label = box.parentElement.previousElementSibling.getBoundingClientRect();
	const input = box.querySelector("input");
	let textLeft;
	if (input) {
		const style = getComputedStyle(input);
		textLeft =
			input.getBoundingClientRect().left +
			parseFloat(style.paddingLeft) +
			parseFloat(style.borderLeftWidth);
	} else {
		const text = box.querySelector("span.truncate, a.truncate");
		const range = document.createRange();
		range.selectNodeContents(text);
		textLeft = range.getBoundingClientRect().left;
	}
	return {
		height: rect.height,
		width: rect.width,
		column: column.width,
		textX: textLeft - rect.left,
		labelTop: label.top - rect.top,
		others: [...document.querySelectorAll(".field-box")]
			.filter((other) => other !== box)
			.map((other) => other.getBoundingClientRect().top - rect.top),
		editing: !!input,
	};
}

test.describe("Desk v2 side panel row", () => {
	let name;

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		await admin.insert_doc(
			"DocType",
			{
				name: DOCTYPE,
				module: "Core",
				custom: 1,
				autoname: "hash",
				fields: TYPES.map(({ label, fieldname, fieldtype, options, placeholder }) => ({
					label,
					fieldname,
					fieldtype,
					options,
					placeholder,
				})),
				permissions: [{ role: "System Manager", read: 1, write: 1, create: 1 }],
			},
			true
		);
		await admin.insert_doc("Form Layout", {
			dt: DOCTYPE,
			type: "Side Panel",
			layout: JSON.stringify(LAYOUT),
		});
		name = (await admin.insert_doc(DOCTYPE, VALUES)).name;
	});

	test.afterAll(async ({ admin }) => {
		const layouts = await admin.get_list("Form Layout", ["name"], [["dt", "=", DOCTYPE]]);
		for (const { name: layout } of layouts.data ?? []) {
			await admin.remove_doc("Form Layout", layout, true);
		}
		await admin.remove_doc(DOCTYPE, name, true);
		await admin.remove_doc("DocType", DOCTYPE, true);
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test.beforeEach(async ({ page }) => {
		await page.goto(`/apps/desk/${SLUG}/${name}`);
		await expect(row(page, "f_data")).toBeVisible();
	});

	for (const { fieldname, label } of TYPES) {
		test(`${label} (${fieldname}) keeps one box in rest, hover and focus`, async ({
			page,
		}) => {
			await row(page, fieldname).scrollIntoViewIfNeeded();
			const rest = await page.evaluate(measure, fieldname);
			await row(page, fieldname).hover();
			const hover = await page.evaluate(measure, fieldname);
			await row(page, fieldname).click();
			await expect(
				page.locator(`.field-box [data-fieldname="${fieldname}"] input`)
			).toBeFocused();
			const focus = await page.evaluate(measure, fieldname);

			expect(rest.editing).toBe(false);
			expect(focus.editing).toBe(true);
			for (const state of [rest, hover, focus]) {
				expect(state.height).toBeCloseTo(28, 1);
				expect(state.column).toBeGreaterThan(150);
				expect(state.width).toBeCloseTo(state.column, 1);
				expect(state.textX).toBeCloseTo(8, 0);
				expect(state.labelTop).toBeCloseTo(0, 1);
				state.others.forEach((top, i) => expect(top).toBeCloseTo(rest.others[i], 1));
			}
		});
	}

	test("a press on a blank part of the page closes the open row", async ({ page }) => {
		await row(page, "f_data").click();
		await expect(page.locator(".field-box input")).toHaveCount(1);
		await page.mouse.click(5, 450);
		await expect(page.locator(".field-box input")).toHaveCount(0);

		await row(page, "f_int").click();
		await row(page, "f_float").click();
		await expect(page.locator(".field-box input")).toHaveCount(1);
		await expect(page.locator('.field-box [data-fieldname="f_float"] input')).toBeVisible();
	});

	test("a Password row draws one dot per character, in the same place as the open input", async ({
		page,
	}) => {
		const dots = () =>
			page.evaluate(() => {
				const cell = document.querySelector('.field-box [data-fieldname="f_password"]');
				const input = cell.querySelector("input");
				const text = input ?? cell.querySelector("span.truncate");
				return {
					count: input ? input.value.length : text.textContent.length,
					masked:
						getComputedStyle(text).webkitTextSecurity === "disc" ||
						input?.type === "password",
				};
			});
		const rest = await dots();
		await row(page, "f_password").click();
		const open = await dots();

		expect(rest).toEqual({ count: 6, masked: true });
		expect(open).toEqual(rest);
	});

	test("an Email row keeps its mail button at the same x when it opens, and text stops before it", async ({
		page,
	}) => {
		// The shell's email button when the reader may write an email, else the mailto arrow.
		const arrow = (fieldname) =>
			row(page, fieldname).locator('[data-slot="field-action"], [data-slot="mail-arrow"]');
		await row(page, "f_email_long").scrollIntoViewIfNeeded();
		await row(page, "f_email_long").hover();
		const rest = await arrow("f_email_long").boundingBox();
		await row(page, "f_email_long").click();
		const input = page.locator('.field-box [data-fieldname="f_email_long"] input');
		await expect(input).toBeFocused();
		const open = await arrow("f_email_long").boundingBox();
		const textRight = await input.evaluate((el) => {
			const style = getComputedStyle(el);
			return el.getBoundingClientRect().right - parseFloat(style.paddingRight);
		});

		expect(open.x).toBeCloseTo(rest.x, 0);
		expect(textRight).toBeLessThanOrEqual(open.x);
	});

	test("a Duration row opens with the caret at the end and no selection", async ({ page }) => {
		await row(page, "f_duration").click();
		const input = page.locator('.field-box [data-fieldname="f_duration"] input');
		await expect(input).toBeFocused();
		await expect
			.poll(() => input.evaluate((el) => [el.selectionStart, el.selectionEnd]))
			.toEqual([6, 6]);
	});

	test("an open row shows the field's own placeholder, else `Add <Label>...`", async ({
		page,
	}) => {
		await row(page, "f_ph").click();
		await expect(page.locator('.field-box [data-fieldname="f_ph"] input')).toHaveValue("");
		await expect(page.locator('.field-box [data-fieldname="f_ph"] input')).toHaveAttribute(
			"placeholder",
			"Enter a nickname"
		);

		await row(page, "f_data").click();
		await expect(page.locator('.field-box [data-fieldname="f_data"] input')).toHaveAttribute(
			"placeholder",
			"Add Data Field..."
		);
	});

	test("hides a child control's own focus outline and ring: the box ring is the only mark", async ({
		page,
	}) => {
		await row(page, "f_data").click();
		const input = page.locator('.field-box [data-fieldname="f_data"] input');
		await expect(input).toBeFocused();
		await input.evaluate((el) => {
			const raw = document.createElement("input");
			raw.id = "raw-control-46998";
			el.parentElement.appendChild(raw);
			raw.focus();
		});
		const marks = await page.evaluate(() => {
			const style = getComputedStyle(document.getElementById("raw-control-46998"));
			return { outline: style.outlineColor, shadow: style.boxShadow };
		});
		expect(marks).toEqual({ outline: "rgba(0, 0, 0, 0)", shadow: "none" });
	});
});

// Check, Rating, Color, Attach and Attach Image act on one click: the control is the row at rest.
const ONE_CLICK_DOCTYPE = "Panel Row 46993";
const ONE_CLICK_SLUG = "panel-row-46993";
const FILE = "/assets/frappe/images/frappe-favicon.svg";
const LONG_FILE = "/assets/frappe/images/ui-states/notification-empty-state.svg";

const ONE_CLICK_TYPES = [
	{ fieldname: "f_check", fieldtype: "Check", label: "Check Field" },
	{ fieldname: "f_check_ro", fieldtype: "Check", label: "Read-only Check", read_only: 1 },
	{ fieldname: "f_rating", fieldtype: "Rating", label: "Rating Field" },
	{ fieldname: "f_rating_ro", fieldtype: "Rating", label: "Read-only Rating", read_only: 1 },
	{ fieldname: "f_color", fieldtype: "Color", label: "Color Field" },
	{ fieldname: "f_color_empty", fieldtype: "Color", label: "Empty Color" },
	{ fieldname: "f_color_ro", fieldtype: "Color", label: "Read-only Color", read_only: 1 },
	{ fieldname: "f_attach", fieldtype: "Attach", label: "Attach Field" },
	{ fieldname: "f_attach_empty", fieldtype: "Attach", label: "Empty Attach" },
	{ fieldname: "f_attach_ro", fieldtype: "Attach", label: "Read-only Attach", read_only: 1 },
	{ fieldname: "f_photo", fieldtype: "Attach Image", label: "Photo" },
	{ fieldname: "f_photo_empty", fieldtype: "Attach Image", label: "Empty Photo" },
	{ fieldname: "f_shown", fieldtype: "Image", label: "Shown Image", options: "f_orphan" },
	{ fieldname: "f_hidden", fieldtype: "Image", label: "Hidden Image", options: "f_photo" },
	{ fieldname: "f_orphan", fieldtype: "Attach Image", label: "Orphan" },
];
const IN_LAYOUT = ONE_CLICK_TYPES.filter((t) => t.fieldname !== "f_orphan").map(
	(t) => t.fieldname
);
const ONE_CLICK_VALUES = {
	f_check: 1,
	f_check_ro: 1,
	f_rating: 0.6,
	f_rating_ro: 0.6,
	f_color: "#3b82f6",
	f_color_ro: "#3b82f6",
	f_attach: LONG_FILE,
	f_attach_ro: LONG_FILE,
	f_photo: FILE,
	f_orphan: FILE,
};
const ONE_CLICK_LAYOUT = [
	{
		name: "tab_1",
		sections: [
			{
				name: "one_click",
				label: "One click",
				columns: [{ name: "column_1", fields: IN_LAYOUT }],
			},
		],
	},
];

// Where each row draws its first mark and its text, relative to the box. A Color row also
// reports the swatch's right edge, to check the 8px gap.
const LEADS = {
	Check: "input[type=checkbox]",
	Rating: "svg",
	Color: '[data-slot="swatch"], span.truncate',
	Attach: "img, span.truncate",
	"Attach Image": "img, span.truncate",
};

function measureOneClick({ fieldname, fieldtype, lead }) {
	const cell = document.querySelector(`.field-box [data-fieldname="${fieldname}"]`);
	const box = cell.closest(".field-box");
	const rect = box.getBoundingClientRect();
	const column = box.parentElement.getBoundingClientRect();
	const label = box.parentElement.previousElementSibling.getBoundingClientRect();
	const first = cell.querySelector(lead).getBoundingClientRect();
	const text = cell.querySelector("span.truncate");
	const textRect = text && document.createRange();
	if (text) textRect.selectNodeContents(text);
	const visible = (el) => el && getComputedStyle(el).opacity !== "0";
	const link = cell.querySelector("a");
	const clear = cell.querySelector('[data-slot="clear"]');
	return {
		height: rect.height,
		width: rect.width,
		column: column.width,
		leadX: first.left - rect.left,
		gap:
			text && fieldtype === "Color" && cell.querySelector('[data-slot="swatch"]')
				? textRect.getBoundingClientRect().left - first.right
				: null,
		linkShown: visible(link?.parentElement),
		clearShown: visible(clear?.parentElement),
		clearRight: clear ? rect.right - clear.getBoundingClientRect().right : null,
		linkRight: link ? rect.right - link.getBoundingClientRect().right : null,
		clearBeforeLink:
			clear && link
				? clear.getBoundingClientRect().right <= link.getBoundingClientRect().left
				: null,
		nameTruncated: text ? text.scrollWidth > text.clientWidth : null,
		nameGap:
			link && text
				? link.parentElement.getBoundingClientRect().left -
				  text.getBoundingClientRect().right
				: null,
		labelTop: label.top - rect.top,
		others: [...document.querySelectorAll(".field-box")]
			.filter((other) => other !== box)
			.map((other) => other.getBoundingClientRect().top - rect.top),
	};
}

test.describe("Desk v2 side panel row: one-click fields", () => {
	let name;

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		await admin.insert_doc(
			"DocType",
			{
				name: ONE_CLICK_DOCTYPE,
				module: "Core",
				custom: 1,
				autoname: "hash",
				fields: ONE_CLICK_TYPES.map(
					({ label, fieldname, fieldtype, options, read_only }) => ({
						label,
						fieldname,
						fieldtype,
						options,
						read_only,
					})
				),
				permissions: [{ role: "System Manager", read: 1, write: 1, create: 1 }],
			},
			true
		);
		await admin.insert_doc("Form Layout", {
			dt: ONE_CLICK_DOCTYPE,
			type: "Side Panel",
			layout: JSON.stringify(ONE_CLICK_LAYOUT),
		});
		name = (await admin.insert_doc(ONE_CLICK_DOCTYPE, ONE_CLICK_VALUES)).name;
	});

	test.afterAll(async ({ admin }) => {
		const layouts = await admin.get_list(
			"Form Layout",
			["name"],
			[["dt", "=", ONE_CLICK_DOCTYPE]]
		);
		for (const { name: layout } of layouts.data ?? []) {
			await admin.remove_doc("Form Layout", layout, true);
		}
		await admin.remove_doc(ONE_CLICK_DOCTYPE, name, true);
		await admin.remove_doc("DocType", ONE_CLICK_DOCTYPE, true);
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test.beforeEach(async ({ page }) => {
		await page.goto(`/apps/desk/${ONE_CLICK_SLUG}/${name}`);
		await expect(row(page, "f_check")).toBeVisible();
	});

	for (const { fieldname, fieldtype, label, read_only } of ONE_CLICK_TYPES) {
		if (fieldtype === "Image" || fieldname === "f_orphan") continue;
		test(`${label} (${fieldname}) keeps one 28px box in rest, hover and focus`, async ({
			page,
		}) => {
			const args = { fieldname, fieldtype, lead: LEADS[fieldtype] };
			await row(page, fieldname).scrollIntoViewIfNeeded();
			const rest = await page.evaluate(measureOneClick, args);
			await row(page, fieldname).hover();
			const hover = await page.evaluate(measureOneClick, args);
			const states = [rest, hover];
			if (!read_only) {
				await row(page, fieldname)
					.locator("input, button, [tabindex='0']")
					.first()
					.focus();
				states.push(await page.evaluate(measureOneClick, args));
			}

			for (const state of states) {
				expect(state.height).toBeCloseTo(28, 1);
				expect(state.column).toBeGreaterThan(150);
				expect(state.width).toBeCloseTo(state.column, 1);
				expect(state.labelTop).toBeCloseTo(0, 1);
				state.others.forEach((top, i) => expect(top).toBeCloseTo(rest.others[i], 1));
				if (fieldtype === "Color" && state.gap !== null)
					expect(state.gap).toBeCloseTo(8, 0);
				if (
					["Check", "Rating", "Color"].includes(fieldtype) ||
					!fieldname.endsWith("_photo")
				)
					expect(state.leadX).toBeCloseTo(8, 0);
			}
		});
	}

	test("Attach and Attach Image keep ↗ at the right edge with × before it on hover, and a read-only Attach only ↗ at the same x", async ({
		page,
	}) => {
		const args = (fieldname, fieldtype) => ({ fieldname, fieldtype, lead: LEADS[fieldtype] });
		for (const fieldname of ["f_attach", "f_photo"]) {
			const fieldtype = fieldname === "f_photo" ? "Attach Image" : "Attach";
			const before = await page.evaluate(measureOneClick, args(fieldname, fieldtype));
			expect(before.linkShown).toBe(false);
			await row(page, fieldname).hover();
			const after = await page.evaluate(measureOneClick, args(fieldname, fieldtype));
			expect(after.linkShown).toBe(true);
			expect(after.clearShown).toBe(true);
			expect(after.linkRight).toBeCloseTo(8, 0);
			expect(after.clearBeforeLink).toBe(true);
			expect(after.nameGap).toBeGreaterThanOrEqual(8);
			if (after.nameTruncated) expect(after.nameGap).toBeCloseTo(8, 0);
			expect(after.height).toBeCloseTo(28, 1);
		}
		const readOnly = await page.evaluate(measureOneClick, args("f_attach_ro", "Attach"));
		expect(readOnly.linkShown).toBe(true);
		expect(readOnly.clearRight).toBeNull();
		expect(readOnly.linkRight).toBeCloseTo(8, 0);
		expect(readOnly.nameTruncated).toBe(true);
		expect(readOnly.nameGap).toBeCloseTo(8, 0);
	});

	test("an empty Attach and Attach Image read `Add <Label>...`", async ({ page }) => {
		await expect(row(page, "f_attach_empty")).toHaveText("Add Empty Attach...");
		await expect(row(page, "f_photo_empty")).toHaveText("Add Empty Photo...");
		await expect(row(page, "f_color_empty")).toHaveText("Add Empty Color...");
	});

	test("an Image row hides when its Attach Image is in the panel, else shows a 20px thumbnail", async ({
		page,
	}) => {
		await expect(row(page, "f_hidden")).toHaveCount(0);
		const thumb = row(page, "f_shown").locator("img");
		const box = await thumb.boundingBox();
		expect(box.width).toBeCloseTo(20, 0);
		expect(box.height).toBeCloseTo(20, 0);
		await expect(row(page, "f_shown")).toContainText("frappe-favicon.svg");
		const rowBox = await row(page, "f_shown")
			.locator("xpath=ancestor::*[contains(@class,'field-box')]")
			.boundingBox();
		expect(rowBox.height).toBeCloseTo(28, 1);

		await row(page, "f_shown").click();
		await expect(page.getByRole("dialog").locator("img")).toBeVisible();
		await expect(page).toHaveURL(new RegExp(`${ONE_CLICK_SLUG}/${name}$`));
	});

	test("a click on the box toggles a Check and the record saves the new value", async ({
		page,
	}) => {
		const checkbox = row(page, "f_check").locator("input[type=checkbox]");
		await expect(checkbox).toBeChecked();
		await row(page, "f_check").click({ position: { x: 150, y: 14 } });
		await expect(checkbox).not.toBeChecked();
		await page.getByRole("button", { name: "Save", exact: true }).click();
		await expect
			.poll(async () => {
				const res = await page.request.get(
					`/api/v2/document/${encodeURIComponent(ONE_CLICK_DOCTYPE)}/${name}`
				);
				return (await res.json()).data.f_check;
			})
			.toBe(0);
	});

	test("a set Color row shows × at the right edge on hover and focus, and a click clears it without opening the picker", async ({
		page,
	}) => {
		const box = row(page, "f_color").locator(
			"xpath=ancestor::*[contains(@class,'field-box')]"
		);
		const clear = box.locator('[data-slot="clear"]');
		const edge = async () => {
			const b = await box.boundingBox();
			const c = await clear.boundingBox();
			return { right: b.x + b.width - (c.x + c.width), size: c.width };
		};
		await expect(clear).toHaveCount(1);
		await expect(clear.locator("xpath=..")).toHaveCSS("opacity", "0");
		const hexX = (await row(page, "f_color").locator("span.truncate").boundingBox()).x;
		await row(page, "f_color").hover();
		await expect(clear.locator("xpath=..")).toHaveCSS("opacity", "1");
		expect((await edge()).right).toBeCloseTo(8, 0);
		expect((await edge()).size).toBeCloseTo(16, 0);
		expect((await row(page, "f_color").locator("span.truncate").boundingBox()).x).toBe(hexX);
		await expect(clear).toHaveAttribute("aria-label", "Clear");
		await expect(clear).toHaveAttribute("title", "Clear");
		await expect(
			row(page, "f_color_ro").locator("xpath=..").locator('[data-slot="clear"]')
		).toHaveCount(0);
		await expect(
			row(page, "f_color_empty").locator("xpath=..").locator('[data-slot="clear"]')
		).toHaveCount(0);
		await page.mouse.move(5, 5);
		await box.locator('button[data-slot="control"]').focus();
		await page.keyboard.press("Tab");
		await expect(clear).toBeFocused();
		await expect(clear.locator("xpath=..")).toHaveCSS("opacity", "1");
		await clear.click();
		await expect(page.locator('[data-slot="color-area"]')).toHaveCount(0);
		await expect(row(page, "f_color")).toHaveText("Add Color Field...");
		await expect(clear).toHaveCount(0);
		await expect(box.locator('button[data-slot="control"]')).toBeFocused();
	});

	test("the open Color picker draws no outline around its rounded card, even when it holds focus", async ({
		page,
	}) => {
		await row(page, "f_color").click();
		await expect(page.locator('[data-slot="color-area"]')).toBeVisible();
		await page.keyboard.press("Tab");
		const outline = await page.evaluate(() => {
			const content = document.querySelector('[data-slot="content"][role="dialog"]');
			content.focus();
			return {
				focused: document.activeElement === content,
				visible: content.matches(":focus-visible"),
				style: getComputedStyle(content).outlineStyle,
			};
		});
		expect(outline).toEqual({ focused: true, visible: true, style: "none" });
	});

	test("a Color row opens its picker below the row and saves when it closes", async ({
		page,
	}) => {
		const box = row(page, "f_color").locator(
			"xpath=ancestor::*[contains(@class,'field-box')]"
		);
		await row(page, "f_color").click();
		const picker = page.locator('[data-slot="color-area"]');
		await expect(picker).toBeVisible();
		const rowRect = await box.boundingBox();
		const pickerRect = await picker.boundingBox();
		expect(pickerRect.y).toBeGreaterThan(rowRect.y + rowRect.height);
		await page.locator('input[data-slot="hex"]').fill("#ce2c2c");
		await page.locator('input[data-slot="hex"]').press("Enter");
		await expect(picker).toHaveCount(0);
		await expect(row(page, "f_color")).toContainText("#ce2c2c");
	});
});

const GROW = "Panel Grow 46994";
const GROW_SLUG = "panel-grow-46994";
const GROW_TAG = "Panel Grow Tag 46994";
const TAGS = ["Alpha", "Beta", "Gamma", "A longer tag name", "Delta", "Epsilon", "Zeta"];
const GROW_FIELDS = [
	{ fieldname: "f_small", fieldtype: "Small Text", label: "Small Field" },
	{ fieldname: "f_text", fieldtype: "Text", label: "Text Field" },
	{ fieldname: "f_long", fieldtype: "Long Text", label: "Long Field" },
	{
		fieldname: "f_hint",
		fieldtype: "Small Text",
		label: "Notes",
		placeholder: "Anything to add?",
	},
	{ fieldname: "f_tags", fieldtype: "Table MultiSelect", label: "Tags", options: GROW_TAG },
	{ fieldname: "f_code", fieldtype: "Code", label: "Code Field" },
	{ fieldname: "f_data", fieldtype: "Data", label: "Data Field" },
	...Array.from({ length: 22 }, (_, i) => ({
		fieldname: `fill_${i}`,
		fieldtype: "Data",
		label: `Filler ${i}`,
	})),
];
const SECTIONS = [
	{ name: "s1", label: "Fields A", fields: ["f_small", "f_text", "f_long", "f_hint"] },
	{
		name: "s2",
		label: "Fields B",
		fields: ["f_tags", "f_code", "f_data", ...GROW_FIELDS.slice(7).map((f) => f.fieldname)],
	},
];
const layoutOf = (sections) => [
	{
		name: "tab_1",
		sections: sections.map(({ name, label, fields }) => ({
			name,
			label,
			columns: [{ name: `${name}_c`, fields }],
		})),
	},
];
const lines = (count) => Array.from({ length: count }, (_, i) => `line ${i + 1}`).join("\n");

// The box of one panel row, read in the page: its height, and its label's and its neighbours' tops.
function boxOf(fieldname) {
	const box = document
		.querySelector(`.field-box [data-fieldname="${fieldname}"]`)
		.closest(".field-box");
	const rect = box.getBoundingClientRect();
	const boxes = [...document.querySelectorAll(".field-box")];
	return {
		height: rect.height,
		labelTop: box.parentElement.previousElementSibling.getBoundingClientRect().top - rect.top,
		above: boxes
			.slice(0, boxes.indexOf(box))
			.map((other) => other.getBoundingClientRect().top),
	};
}

test.describe("Desk v2 side panel rows that grow", () => {
	let filled, empty, scratch;
	const grow = (page, fieldname) => page.locator(`.field-box [data-fieldname="${fieldname}"]`);
	const area = (page, fieldname) => grow(page, fieldname).locator("textarea");
	const open = async (page, name) => {
		await page.goto(`/apps/desk/${GROW_SLUG}/${name}`);
		await expect(grow(page, "f_small")).toBeVisible();
	};

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		const permissions = [{ role: "System Manager", read: 1, write: 1, create: 1 }];
		await admin.insert_doc(
			"DocType",
			{
				name: "Tag 46994",
				module: "Core",
				custom: 1,
				autoname: "field:title",
				fields: [
					{ fieldname: "title", fieldtype: "Data", label: "Title", unique: 1, reqd: 1 },
				],
				permissions,
			},
			true
		);
		for (const title of TAGS) await admin.insert_doc("Tag 46994", { title }, true);
		await admin.insert_doc(
			"DocType",
			{
				name: GROW_TAG,
				module: "Core",
				custom: 1,
				istable: 1,
				fields: [
					{
						fieldname: "tag",
						fieldtype: "Link",
						options: "Tag 46994",
						label: "Tag",
						in_list_view: 1,
					},
				],
			},
			true
		);
		await admin.insert_doc(
			"DocType",
			{
				name: GROW,
				module: "Core",
				custom: 1,
				autoname: "hash",
				fields: GROW_FIELDS.map(
					({ label, fieldname, fieldtype, options, placeholder }) => ({
						label,
						fieldname,
						fieldtype,
						options,
						placeholder,
					})
				),
				permissions,
			},
			true
		);
		await admin.insert_doc("Form Layout", {
			dt: GROW,
			type: "Side Panel",
			layout: JSON.stringify(layoutOf(SECTIONS)),
		});
		// Details draws every field but Code, so Code is the heavy field that edits in place.
		await admin.insert_doc("Form Layout", {
			dt: GROW,
			type: "Details",
			layout: JSON.stringify(
				layoutOf([
					{
						name: "d1",
						label: "Main",
						fields: ["f_small", "f_text", "f_long", "f_hint", "f_tags", "f_data"],
					},
				])
			),
		});
		filled = (
			await admin.insert_doc(GROW, {
				f_small:
					"A long sentence that wraps over a few lines inside the narrow value column of the side panel row for the walk.",
				f_text: lines(3),
				f_long: lines(9),
				f_tags: TAGS.slice(0, 5).map((tag) => ({ tag })),
				f_code: "print('hi')",
			})
		).name;
		empty = (await admin.insert_doc(GROW, { f_data: "empty" })).name;
		scratch = (await admin.insert_doc(GROW, { f_data: "scratch" })).name;
	});

	test.afterAll(async ({ admin }) => {
		const layouts = await admin.get_list("Form Layout", ["name"], [["dt", "=", GROW]]);
		for (const { name } of layouts.data ?? [])
			await admin.remove_doc("Form Layout", name, true);
		for (const name of [filled, empty, scratch]) await admin.remove_doc(GROW, name, true);
		await admin.remove_doc("DocType", GROW, true);
		await admin.remove_doc("DocType", GROW_TAG, true);
		for (const title of TAGS) await admin.remove_doc("Tag 46994", title, true);
		await admin.remove_doc("DocType", "Tag 46994", true);
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	for (const fieldname of ["f_small", "f_text", "f_long"]) {
		test(`an empty ${fieldname} row is 28 high in rest, hover and focus, and the label stays on the first line`, async ({
			page,
		}) => {
			await open(page, empty);
			const rest = await page.evaluate(boxOf, fieldname);
			await grow(page, fieldname).hover();
			const hover = await page.evaluate(boxOf, fieldname);
			await grow(page, fieldname).click();
			await expect(area(page, fieldname)).toBeFocused();
			const focus = await page.evaluate(boxOf, fieldname);

			for (const state of [rest, hover, focus]) {
				expect(state.height).toBeCloseTo(28, 1);
				expect(state.labelTop).toBeCloseTo(0, 1);
				state.above.forEach((top, i) => expect(top).toBeCloseTo(rest.above[i], 1));
			}
		});
	}

	test("typing grows the row 20 per line up to 128, then scrolls", async ({ page }) => {
		await open(page, empty);
		await grow(page, "f_text").click();
		const text = area(page, "f_text");
		await expect(text).toBeFocused();
		const rest = await page.evaluate(boxOf, "f_text");
		const heights = [];
		for (let line = 1; line <= 8; line++) {
			if (line > 1) await page.keyboard.press("Enter");
			await page.keyboard.type(`line ${line}`);
			const state = await page.evaluate(boxOf, "f_text");
			heights.push(state.height);
			expect(state.labelTop).toBeCloseTo(0, 1);
			state.above.forEach((top, i) => expect(top).toBeCloseTo(rest.above[i], 1));
		}

		expect(heights.map(Math.round)).toEqual([28, 48, 68, 88, 108, 128, 128, 128]);
		expect(await text.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);
	});

	for (const [fieldname, height] of [
		["f_small", 0],
		["f_text", 68],
		["f_long", 128],
	]) {
		test(`a filled ${fieldname} row keeps its height when it opens`, async ({ page }) => {
			await open(page, filled);
			await grow(page, fieldname).scrollIntoViewIfNeeded();
			const rest = await page.evaluate(boxOf, fieldname);
			await grow(page, fieldname).click();
			await expect(area(page, fieldname)).toBeFocused();
			const opened = await page.evaluate(boxOf, fieldname);

			expect(opened.height).toBeCloseTo(rest.height, 1);
			expect(opened.labelTop).toBeCloseTo(0, 1);
			opened.above.forEach((top, i) => expect(top).toBeCloseTo(rest.above[i], 1));
			if (height) expect(rest.height).toBeCloseTo(height, 1);
			else expect(rest.height).toBeGreaterThan(28);
			expect(rest.height).toBeLessThanOrEqual(128);
		});
	}

	test("a Long Text row of 9 lines opens on the lines it showed at rest, the caret where it was clicked", async ({
		page,
	}) => {
		await open(page, filled);
		const long = grow(page, "f_long");
		await long.scrollIntoViewIfNeeded();
		const rest = await long.evaluate((el) => {
			const text = el.querySelector(".line-clamp-6");
			const top = text.getBoundingClientRect().top;
			return { top, first: text.textContent.split("\n")[0] };
		});
		const box = await long.boundingBox();
		await page.mouse.click(box.x + 30, box.y + 4 + 20 * 1.5);
		const text = area(page, "f_long");
		await expect(text).toBeFocused();

		const opened = await text.evaluate((el) => ({
			scrollTop: el.scrollTop,
			first: el.value.split("\n")[Math.round(el.scrollTop / 20)],
			caretLine: el.value.slice(0, el.selectionStart).split("\n").length,
			end: el.selectionStart === el.value.length,
		}));
		expect(opened.first).toBe(rest.first);
		expect(opened.scrollTop).toBe(0);
		expect(opened.caretLine).toBe(2);
		expect(opened.end).toBe(false);
	});

	test("Tab commits the text and closes the row; Esc cancels it", async ({ page }) => {
		await open(page, scratch);
		await grow(page, "f_hint").click();
		await expect(area(page, "f_hint")).toHaveAttribute("placeholder", "Anything to add?");
		await page.keyboard.type("first");
		await page.keyboard.press("Enter");
		await page.keyboard.type("second");
		await page.keyboard.press("Tab");
		await expect(page.locator(".field-box textarea")).toHaveCount(0);
		await expect(grow(page, "f_hint")).toContainText("first");
		await expect(grow(page, "f_hint")).toContainText("second");

		await grow(page, "f_hint").click();
		await page.keyboard.type(" gone");
		await page.keyboard.press("Escape");
		await expect(page.locator(".field-box textarea")).toHaveCount(0);
		await expect(grow(page, "f_hint")).not.toContainText("gone");
		await expect(grow(page, "f_hint")).toContainText("second");
	});

	test("a Table MultiSelect row keeps its height and its chips in place when it opens", async ({
		page,
	}) => {
		await open(page, filled);
		await grow(page, "f_tags").scrollIntoViewIfNeeded();
		const chips = () =>
			grow(page, "f_tags").evaluate((cell) =>
				[...cell.querySelectorAll("span.inline-flex.h-5")].map((chip) => {
					const { x, y, width } = chip.getBoundingClientRect();
					return [x, y, width].map(Math.round);
				})
			);
		const rest = await page.evaluate(boxOf, "f_tags");
		const restChips = await chips();
		await grow(page, "f_tags").click();
		// Open, each chip's × is live instead of held as space.
		await expect(
			grow(page, "f_tags").locator('[role="button"]:not(.invisible)').first()
		).toBeVisible();
		const opened = await page.evaluate(boxOf, "f_tags");

		expect(restChips).toHaveLength(5);
		expect(opened.height).toBeCloseTo(rest.height, 1);
		expect(await chips()).toEqual(restChips);
	});

	// Open, each chip's × is live and drawn above static content, so only the header's z-index keeps it under the bar.
	for (const state of ["at rest", "open"]) {
		test(`a pinned section header covers a chip row scrolled under it, ${state}`, async ({
			page,
		}) => {
			await open(page, filled);
			if (state === "open") await grow(page, "f_tags").click();
			const covered = await page.evaluate(() => {
				const cell = document.querySelector('.field-box [data-fieldname="f_tags"]');
				let scroller = cell.parentElement;
				while (!/(auto|scroll)/.test(getComputedStyle(scroller).overflowY))
					scroller = scroller.parentElement;
				// The identity block pins above the section headers, so aim at the first header's edge.
				const pinned = Math.min(
					...[...document.querySelectorAll("[data-section].sticky")].map(
						(header) => header.getBoundingClientRect().bottom
					)
				);
				scroller.scrollTop += cell.getBoundingClientRect().top - pinned + 20;
				return new Promise((resolve) =>
					requestAnimationFrame(() => {
						const chips = [...cell.querySelectorAll("span.inline-flex")];
						const headers = [...document.querySelectorAll("[data-section].sticky")];
						const checks = headers.flatMap((header) => {
							const bar = header.getBoundingClientRect();
							return chips
								.map((chip) => chip.getBoundingClientRect())
								.map((chip) => [
									Math.max(chip.top, bar.top),
									Math.min(chip.bottom, bar.bottom),
									chip.left,
								])
								.filter(([top, bottom]) => bottom - top >= 2)
								.map(([top, bottom, left]) => {
									const at = document.elementFromPoint(
										left + 8,
										(top + bottom) / 2
									);
									return at?.closest("[data-section]") === header;
								});
						});
						resolve({ headers: headers.length, checks });
					})
				);
			});

			expect(covered.headers).toBe(2);
			expect(covered.checks.length).toBeGreaterThan(0);
			expect(covered.checks.every(Boolean)).toBe(true);
		});
	}

	test("a heavy field that Details does not draw edits in place", async ({ page }) => {
		await open(page, filled);
		await grow(page, "f_code").scrollIntoViewIfNeeded();
		await grow(page, "f_code").click();

		await expect(grow(page, "f_code").locator(".cm-editor")).toBeVisible();
	});
});

// A required mark sits 2px after the label, a cut-off one included.
const LABEL_DOCTYPE = "Panel Label 46995";
const LABEL_SLUG = "panel-label-46995";
const LONG_LABEL = "Preferred communication channel for billing address";
const LABEL_TYPES = [
	{ fieldname: "f_short", fieldtype: "Data", label: "Title", reqd: 1 },
	{ fieldname: "f_long", fieldtype: "Data", label: LONG_LABEL, reqd: 1 },
];
const LABEL_LAYOUT = [
	{
		name: "tab_1",
		sections: [
			{
				name: "labels",
				label: "Labels",
				columns: [{ name: "column_1", fields: LABEL_TYPES.map((t) => t.fieldname) }],
			},
		],
	},
];

function measureLabelGap(fieldname) {
	const box = document
		.querySelector(`.field-box [data-fieldname="${fieldname}"]`)
		.closest(".field-box");
	const label = box.parentElement.previousElementSibling;
	const text = label.firstElementChild;
	const star = label.querySelector('[role="img"]');
	const range = document.createRange();
	range.selectNodeContents(text);
	return {
		text: text.textContent,
		gap: star.getBoundingClientRect().left - range.getBoundingClientRect().right,
		labelRight: label.getBoundingClientRect().right,
		starRight: star.getBoundingClientRect().right,
	};
}

test.describe("Desk v2 side panel row: required label gap", () => {
	let name;

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		await admin.insert_doc(
			"DocType",
			{
				name: LABEL_DOCTYPE,
				module: "Core",
				custom: 1,
				autoname: "hash",
				fields: LABEL_TYPES,
				permissions: [{ role: "System Manager", read: 1, write: 1, create: 1 }],
			},
			true
		);
		await admin.insert_doc("Form Layout", {
			dt: LABEL_DOCTYPE,
			type: "Side Panel",
			layout: JSON.stringify(LABEL_LAYOUT),
		});
		name = (await admin.insert_doc(LABEL_DOCTYPE, { f_short: "a", f_long: "b" })).name;
	});

	test.afterAll(async ({ admin }) => {
		const layouts = await admin.get_list(
			"Form Layout",
			["name"],
			[["dt", "=", LABEL_DOCTYPE]]
		);
		for (const { name: layout } of layouts.data ?? []) {
			await admin.remove_doc("Form Layout", layout, true);
		}
		await admin.remove_doc(LABEL_DOCTYPE, name, true);
		await admin.remove_doc("DocType", LABEL_DOCTYPE, true);
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("the mark is 2px after a full label and after a cut-off one", async ({ page }) => {
		await page.goto(`/apps/desk/${LABEL_SLUG}/${name}`);
		await expect(row(page, "f_short")).toBeVisible();
		const full = await page.evaluate(measureLabelGap, "f_short");
		const cut = await page.evaluate(measureLabelGap, "f_long");
		expect(full.text).toBe("Title");
		expect(cut.text.endsWith("…")).toBe(true);
		expect(cut.text.length).toBeLessThan(LONG_LABEL.length);
		expect(full.gap).toBeCloseTo(2, 1);
		expect(cut.gap).toBeCloseTo(2, 1);
		// The mark stays inside the label column when the text is cut.
		expect(cut.starRight).toBeLessThanOrEqual(cut.labelRight + 0.5);
	});
});

const PICKER_DOCTYPE = "Panel Picker 46992";
const PICKER_SLUG = "panel-picker-46992";

const LONG_OPTION = "A very long option that cannot fit in the value column of the panel";
const LONG_ROLE = "Role With A Rather Long Name For The Panel Picker 46992";

const PICKERS = [
	{ fieldname: "p_link", fieldtype: "Link", options: "Role", label: "Link Field" },
	{ fieldname: "p_type", fieldtype: "Link", options: "DocType", label: "Type Field" },
	{
		fieldname: "p_dynamic",
		fieldtype: "Dynamic Link",
		options: "p_type",
		label: "Dynamic Field",
	},
	{
		fieldname: "p_select",
		fieldtype: "Select",
		options: `Draft\nOpen\nClosed\n${LONG_OPTION}`,
		label: "Select Field",
	},
	{
		fieldname: "p_auto",
		fieldtype: "Autocomplete",
		options: "Alpha\nBeta\nGamma",
		label: "Autocomplete Field",
	},
	{ fieldname: "p_date", fieldtype: "Date", label: "Date Field" },
	{ fieldname: "p_datetime", fieldtype: "Datetime", label: "Datetime Field" },
	{ fieldname: "p_time", fieldtype: "Time", label: "Time Field" },
];
// Rows the geometry loop skips: a Link whose target gives a mark, and a read-only Select.
const PICKER_EXTRAS = [
	{ fieldname: "p_user", fieldtype: "Link", options: "User", label: "User Link" },
	{
		fieldname: "p_long",
		fieldtype: "Link",
		options: "DocType",
		label: "Dynamic Link target field",
	},
	{
		fieldname: "p_ro",
		fieldtype: "Select",
		options: "Draft\nOpen",
		label: "Read Only",
		read_only: 1,
	},
];
const PICKER_VALUES = {
	p_user: "Administrator",
	p_ro: "Open",
	p_link: "System Manager",
	p_type: "Role",
	p_dynamic: "System Manager",
	p_select: "Open",
	p_auto: "Beta",
	p_date: "2026-11-11",
	p_datetime: "2026-11-11 09:30:00",
	p_time: "09:30:00",
};
const PICKER_LAYOUT = [
	{
		name: "tab_1",
		sections: [
			{
				name: "pickers",
				label: "Pickers",
				columns: [
					{
						name: "column_1",
						fields: [...PICKERS, ...PICKER_EXTRAS].map((p) => p.fieldname),
					},
				],
			},
		],
	},
];
const POPOVER = "[data-reka-popper-content-wrapper]";
const DATE_LIKE = ["p_date", "p_datetime", "p_time"];

// What a picker's controls draw inside its row: they must add no fill, border or ring of their own.
function measureInnerBoxes(fieldname) {
	const box = document
		.querySelector(`.field-box [data-fieldname="${fieldname}"]`)
		.closest(".field-box");
	const width = box.getBoundingClientRect().width;
	return [
		...box.querySelectorAll(
			'[data-slot="trigger"], [data-slot="control"], [data-slot="input"]'
		),
	].map((el) => {
		const style = getComputedStyle(el);
		const rings = [
			...style.boxShadow.matchAll(/(-?[\d.]+)px (-?[\d.]+)px (-?[\d.]+)px (-?[\d.]+)px/g),
		];
		return {
			slot: el.dataset.slot,
			width: el.getBoundingClientRect().width,
			boxWidth: width,
			fill: style.backgroundColor,
			border: style.borderTopWidth,
			ring: rings.every((m) => m.slice(1).every((n) => parseFloat(n) === 0)),
			outline: style.outlineStyle === "none" || style.outlineColor === "rgba(0, 0, 0, 0)",
		};
	});
}

function expectOneBox(inner) {
	expect(inner.length).toBeGreaterThan(0);
	for (const el of inner) {
		expect(el.fill).toBe("rgba(0, 0, 0, 0)");
		expect(el.border).toBe("0px");
		expect(el.ring).toBe(true);
		expect(el.outline).toBe(true);
		if (el.slot !== "input") expect(el.width).toBeCloseTo(el.boxWidth, 1);
	}
}

// The geometry of one picker row. An open picker has an input to type in, or only a trigger (Select).
function measurePicker(fieldname) {
	const cell = document.querySelector(`.field-box [data-fieldname="${fieldname}"]`);
	const box = cell.closest(".field-box");
	const rect = box.getBoundingClientRect();
	const column = box.parentElement.getBoundingClientRect();
	const input = box.querySelector("input");
	let textLeft;
	if (input) {
		const style = getComputedStyle(input);
		textLeft =
			input.getBoundingClientRect().left +
			parseFloat(style.paddingLeft) +
			parseFloat(style.borderLeftWidth);
	} else {
		const scope = box.querySelector('[data-slot="trigger"]') ?? box;
		const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
		let node = walker.nextNode();
		while (node && !node.textContent.trim()) node = walker.nextNode();
		const range = document.createRange();
		range.selectNodeContents(node);
		textLeft = range.getBoundingClientRect().left;
	}
	return {
		height: rect.height,
		width: rect.width,
		column: column.width,
		textX: textLeft - rect.left,
	};
}

test.describe("Desk v2 side panel picker rows", () => {
	let name;
	let emptyName;

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		await admin.insert_doc(
			"DocType",
			{
				name: PICKER_DOCTYPE,
				module: "Core",
				custom: 1,
				autoname: "hash",
				fields: [...PICKERS, ...PICKER_EXTRAS].map(
					({ label, fieldname, fieldtype, options, read_only }) => ({
						label,
						fieldname,
						fieldtype,
						options,
						read_only,
					})
				),
				permissions: [{ role: "System Manager", read: 1, write: 1, create: 1 }],
			},
			true
		);
		await admin.insert_doc("Form Layout", {
			dt: PICKER_DOCTYPE,
			type: "Side Panel",
			layout: JSON.stringify(PICKER_LAYOUT),
		});
		await admin.insert_doc("Role", { role_name: LONG_ROLE }, true);
		name = (await admin.insert_doc(PICKER_DOCTYPE, PICKER_VALUES)).name;
		emptyName = (await admin.insert_doc(PICKER_DOCTYPE, {})).name;
	});

	test.afterAll(async ({ admin }) => {
		const layouts = await admin.get_list(
			"Form Layout",
			["name"],
			[["dt", "=", PICKER_DOCTYPE]]
		);
		for (const { name: layout } of layouts.data ?? []) {
			await admin.remove_doc("Form Layout", layout, true);
		}
		for (const doc of [name, emptyName]) await admin.remove_doc(PICKER_DOCTYPE, doc, true);
		await admin.remove_doc("DocType", PICKER_DOCTYPE, true);
		await admin.remove_doc("Role", LONG_ROLE, true);
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	const cell = (page, fieldname) => page.locator(`.field-box [data-fieldname="${fieldname}"]`);

	test.beforeEach(async ({ page }) => {
		await page.goto(`/apps/desk/${PICKER_SLUG}/${name}`);
		await expect(cell(page, "p_link")).toBeVisible();
	});

	for (const { fieldname, label } of PICKERS) {
		test(`${label} (${fieldname}) keeps one box and opens its popover on the first click`, async ({
			page,
		}) => {
			await cell(page, fieldname).scrollIntoViewIfNeeded();
			const rest = await page.evaluate(measurePicker, fieldname);
			await cell(page, fieldname).hover();
			const hover = await page.evaluate(measurePicker, fieldname);
			await cell(page, fieldname).click();
			await expect(page.locator(POPOVER)).toBeVisible();
			const focus = await page.evaluate(measurePicker, fieldname);

			for (const state of [rest, hover, focus]) {
				expect(state.height).toBeCloseTo(28, 1);
				expect(state.column).toBeGreaterThan(150);
				expect(state.width).toBeCloseTo(state.column, 1);
				expect(state.textX).toBeCloseTo(8, 0);
			}
			const box = await page
				.locator(`.field-box:has([data-fieldname="${fieldname}"])`)
				.boundingBox();
			const popover = await page.locator(POPOVER).boundingBox();
			// A date picker keeps its own width; the page edge may shift any popover left, but not out of the panel.
			const panel = await page.locator(".panel-layout").boundingBox();
			expect(popover.x).toBeGreaterThanOrEqual(Math.min(box.x - 12, panel.x));
			expect(popover.x).toBeLessThanOrEqual(box.x + 1);
			if (!DATE_LIKE.includes(fieldname)) {
				expect(popover.width).toBeGreaterThanOrEqual(box.width - 1);
			}
		});
	}

	for (const [fieldname, search, text] of [
		["p_link", "Role With A Rather", LONG_ROLE],
		["p_select", "", LONG_OPTION],
	]) {
		test(`${fieldname}'s list stays inside the panel, truncates a long option and titles it`, async ({
			page,
		}) => {
			await cell(page, fieldname).click();
			if (search) {
				await page.keyboard.press("Control+A");
				await page.keyboard.type(search);
			}
			const option = page.locator(`${POPOVER} [role="option"]`, { hasText: text });
			await option.hover();
			const popover = await page.locator(POPOVER).boundingBox();
			const panel = await page.locator(".panel-layout").boundingBox();
			expect(popover.x).toBeGreaterThanOrEqual(panel.x - 0.5);
			expect(popover.x + popover.width).toBeLessThanOrEqual(panel.x + panel.width + 1);
			await expect(option).toHaveAttribute("title", text);
			const truncated = await option
				.locator(".truncate")
				.evaluate((label) => label.scrollWidth > label.clientWidth);
			expect(truncated).toBe(true);
		});
	}

	test("a picker's chevron does not turn when its list opens", async ({ page }) => {
		await cell(page, "p_auto").click();
		await expect(page.locator(POPOVER)).toBeVisible();
		const chevron = cell(page, "p_auto").locator('[data-slot="chevron"]');
		expect(await chevron.evaluate((el) => getComputedStyle(el).transform)).toMatch(
			/^(none|matrix\(1, 0, 0, 1, 0, 0\))$/
		);
	});

	for (const { fieldname, label } of PICKERS) {
		test(`${label} (${fieldname}) draws one box: its control adds no fill, border or ring inside the row's`, async ({
			page,
		}) => {
			await cell(page, fieldname).click();
			await expect(page.locator(POPOVER)).toBeVisible();
			expectOneBox(await page.evaluate(measureInnerBoxes, fieldname));
		});
	}

	// Closed with focus left in the row, a control used to draw its own ring over the row's. Esc ends an
	// Autocomplete's edit, so it closes through its chevron; Esc closes only a Select's list.
	for (const [fieldname, close] of [
		["p_select", (page) => page.keyboard.press("Escape")],
		["p_auto", (page) => cell(page, "p_auto").locator("button").last().click()],
	]) {
		test(`${fieldname} draws one box when its list is closed and the row has focus`, async ({
			page,
		}) => {
			await cell(page, fieldname).click();
			await expect(page.locator(POPOVER)).toBeVisible();
			await close(page);
			await expect(page.locator(POPOVER)).toHaveCount(0);
			expectOneBox(await page.evaluate(measureInnerBoxes, fieldname));
		});
	}

	test("a placeholder too long for the box ends in an ellipsis, also while the row has focus", async ({
		page,
	}) => {
		const input = page.locator('.field-box [data-fieldname="p_long"] input');
		await cell(page, "p_long").click();
		await expect(input).toHaveAttribute("placeholder", /…$/);
		expect(await input.evaluate((el) => getComputedStyle(el).textOverflow)).toBe("ellipsis");
		// Chromium cuts a focused input's placeholder hard, so the text itself must fit and end in "…".
		const { fits, focused } = await input.evaluate((el) => {
			const probe = document.createElement("canvas").getContext("2d");
			const style = getComputedStyle(el);
			probe.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
			const room =
				el.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
			return {
				fits: probe.measureText(el.placeholder).width <= room + 0.5,
				focused: document.activeElement === el,
			};
		});
		expect(focused).toBe(true);
		expect(fits).toBe(true);
	});

	for (const [fieldname, label] of [
		["p_dynamic", "Dynamic Link"],
		["p_link", "Link"],
		["p_select", "Select"],
		["p_auto", "Autocomplete"],
	]) {
		for (const below of [60, 14]) {
			test(`a ${label} list opens below its row and inside the window with ${below}px left under the row`, async ({
				page,
			}) => {
				await cell(page, fieldname).scrollIntoViewIfNeeded();
				const bottom = await cell(page, fieldname).evaluate(
					(el) => el.closest(".field-box").getBoundingClientRect().bottom
				);
				await page.setViewportSize({ width: 1440, height: Math.round(bottom) + below });
				await cell(page, fieldname).click();
				await expect(page.locator(POPOVER)).toBeVisible();
				await page.waitForTimeout(300);
				const { row, list } = await page.evaluate((fieldname) => {
					const rect = (el) => el.getBoundingClientRect();
					return {
						row: rect(
							document
								.querySelector(`.field-box [data-fieldname="${fieldname}"]`)
								.closest(".field-box")
						),
						list: rect(document.querySelector('[data-slot="content"]')),
					};
				}, fieldname);
				expect(list.top).toBeGreaterThanOrEqual(row.bottom);
				expect(list.bottom).toBeLessThanOrEqual(page.viewportSize().height);
			});
		}
	}

	test("a Dynamic Link with no doctype stays closed and does not throw", async ({ page }) => {
		const errors = [];
		page.on("pageerror", (error) => errors.push(error.message));
		await page.goto(`/apps/desk/${PICKER_SLUG}/${emptyName}`);
		await expect(cell(page, "p_dynamic")).toBeVisible();
		await cell(page, "p_dynamic").click();
		await expect(page.locator(POPOVER)).toHaveCount(0);
		expect(errors).toEqual([]);
	});

	test("Esc and a press outside close the open popover", async ({ page }) => {
		for (const fieldname of ["p_select", "p_link", "p_date"]) {
			for (const close of [
				() => page.keyboard.press("Escape"),
				() => page.mouse.click(5, 450),
			]) {
				await cell(page, fieldname).click();
				await expect(page.locator(POPOVER)).toBeVisible();
				await close();
				await expect(page.locator(POPOVER)).toHaveCount(0);
			}
		}
	});

	test("a read-only picker row opens nothing", async ({ page }) => {
		await cell(page, "p_ro").click();
		await expect(page.locator(POPOVER)).toHaveCount(0);
		await expect(
			page.locator(
				`.field-box [data-fieldname="p_ro"] input, .field-box [data-fieldname="p_ro"] [data-slot="trigger"]`
			)
		).toHaveCount(0);
	});

	test("a Link's mark hides while typing and returns, and sits 6px before the text", async ({
		page,
	}) => {
		const state = () =>
			page.evaluate(() => {
				const box = document
					.querySelector('.field-box [data-fieldname="p_user"]')
					.closest(".field-box");
				const mark = box.querySelector("[data-slot=link-mark]");
				const input = box.querySelector("input");
				const origin = box.getBoundingClientRect().left;
				let text;
				if (input) {
					const style = getComputedStyle(input);
					text =
						input.getBoundingClientRect().left +
						parseFloat(style.paddingLeft) +
						parseFloat(style.borderLeftWidth);
				} else {
					const range = document.createRange();
					range.selectNodeContents(box.querySelector("span.truncate"));
					text = range.getBoundingClientRect().left;
				}
				return {
					height: box.getBoundingClientRect().height,
					markRight: mark && mark.getBoundingClientRect().right - origin,
					markX: mark && mark.getBoundingClientRect().left - origin,
					textX: text - origin,
				};
			});
		const rest = await state();
		await cell(page, "p_user").click();
		await expect(page.locator('.field-box [data-fieldname="p_user"] input')).toBeFocused();
		const open = await state();
		await page.keyboard.type("Gue");
		const typing = await state();
		await page.keyboard.press("Escape");
		const back = await state();

		for (const shown of [rest, open, back]) {
			expect(shown.height).toBeCloseTo(28, 1);
			expect(shown.markX).toBeCloseTo(8, 0);
			expect(shown.textX - shown.markRight).toBeCloseTo(6, 0);
		}
		expect(typing.markX).toBeNull();
		expect(typing.textX).toBeCloseTo(8, 0);
		expect(typing.height).toBeCloseTo(28, 1);
	});
});
