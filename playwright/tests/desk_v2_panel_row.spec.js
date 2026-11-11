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
