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
});

// Check, Rating, Color, Attach and Attach Image act on one click: the control is the row at rest.
const ONE_CLICK_DOCTYPE = "Panel Row 46993";
const ONE_CLICK_SLUG = "panel-row-46993";
const FILE = "/assets/frappe/images/frappe-favicon.svg";

const ONE_CLICK_TYPES = [
	{ fieldname: "f_check", fieldtype: "Check", label: "Check Field" },
	{ fieldname: "f_check_ro", fieldtype: "Check", label: "Read-only Check", read_only: 1 },
	{ fieldname: "f_rating", fieldtype: "Rating", label: "Rating Field" },
	{ fieldname: "f_rating_ro", fieldtype: "Rating", label: "Read-only Rating", read_only: 1 },
	{ fieldname: "f_color", fieldtype: "Color", label: "Color Field" },
	{ fieldname: "f_color_empty", fieldtype: "Color", label: "Empty Color" },
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
	f_attach: FILE,
	f_attach_ro: FILE,
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

	test("Attach and Attach Image show ↗ and × on hover, inside the box, and a read-only Attach only ↗", async ({
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
			expect(after.clearRight).toBeCloseTo(8, 0);
			expect(after.height).toBeCloseTo(28, 1);
		}
		const readOnly = await page.evaluate(measureOneClick, args("f_attach_ro", "Attach"));
		expect(readOnly.linkShown).toBe(true);
		expect(readOnly.clearRight).toBeNull();
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
