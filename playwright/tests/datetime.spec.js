import { test, expect } from "../support";
import datetime_doctype from "../fixtures/datetime_doctype";

const doctype_name = datetime_doctype.name;

// the picker rewrites the input from its own selection once its show transition ends,
// so anything typed before that is lost
async function open_picker(page, input) {
	await input.click();
	await expect(page.locator(".datepickers-container .datepicker.active")).toHaveCSS(
		"opacity",
		"1"
	);
}

async function fill_picker_field(page, desk, fieldname, value, fieldtype) {
	const input = desk.get_field(fieldname, fieldtype);
	await open_picker(page, input);
	if (fieldtype === "Time") {
		await input.clear();
	}
	await input.pressSequentially(value, { delay: 20 });
	return input;
}

test.describe("Control Date, Time and DateTime", () => {
	let original_formats;

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", datetime_doctype, true);
		const settings = (await admin.get_doc("System Settings", "System Settings")).data;
		original_formats = {
			date_format: settings.date_format,
			time_format: settings.time_format,
		};
	});

	test.afterAll(async ({ admin }) => {
		await admin.set_value("System Settings", "System Settings", original_formats);
	});

	test.describe("Date formats", () => {
		const date_formats = [
			{
				date_format: "dd-mm-yyyy",
				part: 2,
				length: 4,
				separator: "-",
			},
			{
				date_format: "mm/dd/yyyy",
				part: 0,
				length: 2,
				separator: "/",
			},
		];

		for (const d of date_formats) {
			test("test date format " + d.date_format, async ({ page, desk, admin }) => {
				await admin.set_value("System Settings", "System Settings", {
					date_format: d.date_format,
				});

				await desk.new_form(doctype_name);
				await page.locator(".form-control[data-fieldname=date]").focus();
				const datepicker = page.locator(".datepickers-container .datepicker.active");
				await expect(datepicker).toBeVisible();
				await datepicker.locator(".datepicker--cell-day.-current-").click();

				await expect
					.poll(async () => {
						const formatted_value = await page.evaluate(
							() => cur_frm.get_field("date").input.value
						);
						return formatted_value.split(d.separator)[d.part]?.length;
					})
					.toBe(d.length);
			});
		}
	});

	test.describe("Time formats", () => {
		const time_formats = [
			{
				time_format: "HH:mm:ss",
				value: "  11:00:12",
				match_value: "11:00:12",
			},
			{
				time_format: "HH:mm",
				value: "  11:00:12",
				match_value: "11:00",
			},
		];

		for (const d of time_formats) {
			test("test time format " + d.time_format, async ({ page, desk, admin }) => {
				await admin.set_value("System Settings", "System Settings", {
					time_format: d.time_format,
				});
				await desk.new_form(doctype_name);
				const input = await fill_picker_field(page, desk, "time", d.value, "Time");
				await input.blur();
				await expect(desk.get_field("time")).toHaveValue(d.match_value);
			});
		}

		test("keeps a typed time when the field is focused again", async ({
			page,
			desk,
			admin,
		}) => {
			await admin.set_value("System Settings", "System Settings", {
				time_format: "HH:mm:ss",
			});
			await desk.new_form(doctype_name);
			const input = await fill_picker_field(page, desk, "time", "10:00:00", "Time");
			await input.blur();

			// overwrite without emptying the input, so the picker is not cleared in between
			await open_picker(page, input);
			await input.press("ControlOrMeta+a");
			await input.pressSequentially("11:00:00", { delay: 100 });
			await input.blur();
			await expect.poll(() => page.evaluate(() => cur_frm.doc.time)).toBe("11:00:00");

			await open_picker(page, input);
			await expect(input).toHaveValue("11:00:00");
			await input.blur();
			await expect.poll(() => page.evaluate(() => cur_frm.doc.time)).toBe("11:00:00");
		});
	});

	test.describe("DateTime formats", () => {
		const datetime_formats = [
			{
				date_format: "dd.mm.yyyy",
				time_format: "HH:mm:ss",
				value: "   02.12.2019 11:00:12",
				doc_value: "2019-12-02 00:30:12", // system timezone (America/New_York)
				input_value: "02.12.2019 11:00:12", // user timezone (Asia/Kolkata)
			},
			{
				date_format: "mm-dd-yyyy",
				time_format: "HH:mm",
				value: "   12-02-2019 11:00:00",
				doc_value: "2019-12-02 00:30:00", // system timezone (America/New_York)
				input_value: "12-02-2019 11:00", // user timezone (Asia/Kolkata)
			},
		];

		for (const d of datetime_formats) {
			test(`test datetime format ${d.date_format} ${d.time_format}`, async ({
				page,
				desk,
				admin,
			}) => {
				await admin.set_value("System Settings", "System Settings", {
					date_format: d.date_format,
					time_format: d.time_format,
				});
				await desk.new_form(doctype_name);
				const input = await fill_picker_field(page, desk, "datetime", d.value, "Datetime");
				await input.blur();
				await expect(desk.get_field("datetime")).toHaveValue(d.input_value);

				await expect
					.poll(() => page.evaluate(() => cur_frm.doc.datetime))
					.toBe(d.doc_value);
			});
		}

		test("synchronizes datepicker state when the control is reused", async ({
			page,
			desk,
		}) => {
			await page.goto("/desk/website");
			await desk.ready();

			const state = await page.evaluate(() => {
				const dialog = new frappe.ui.Dialog({
					fields: [
						{
							fieldname: "datetime",
							fieldtype: "Datetime",
							label: "Datetime",
						},
					],
				});
				dialog.show();

				const control = dialog.get_field("datetime");
				const refreshed_value = "2026-07-02 09:15:30";

				// Form controls receive their new model value before set_input is called.
				// Simulate two document refreshes on the same control instance.
				control.value = "2026-07-01 11:30:00";
				control.set_input(control.value);
				control.value = refreshed_value;
				control.set_input(control.value);

				const expected_date = frappe.datetime.user_to_obj(
					control.format_for_input(refreshed_value)
				);
				const state = {
					expected: {
						time: expected_date.getTime(),
						hours: expected_date.getHours(),
						minutes: expected_date.getMinutes(),
						seconds: expected_date.getSeconds(),
					},
					selected_date: control.datepicker.selectedDates[0].getTime(),
					last_selected_date: control.datepicker.lastSelectedDate.getTime(),
					date: control.datepicker.date.getTime(),
					hours: Number(control.datepicker.timepicker.hours),
					minutes: Number(control.datepicker.timepicker.minutes),
					seconds: Number(control.datepicker.timepicker.seconds),
				};

				dialog.hide();
				return state;
			});

			expect(state.selected_date).toBe(state.expected.time);
			expect(state.last_selected_date).toBe(state.expected.time);
			expect(state.date).toBe(state.expected.time);
			expect(state.hours).toBe(state.expected.hours);
			expect(state.minutes).toBe(state.expected.minutes);
			expect(state.seconds).toBe(state.expected.seconds);
		});
	});

	test("accepts the datetime and time values the server sends", async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();

		const validate = (value) =>
			page.evaluate((value) => frappe.datetime.validate(value), value);
		expect(await validate("2026-09-10 06:04:32.450382")).toBe(true);
		expect(await validate("2026-09-10 06:04:32")).toBe(true);
		expect(await validate("6:07:52")).toBe(true);
		expect(await validate("6:07:2.5")).toBe(true);
		expect(await validate("2026-09-10 06:04:32.")).toBe(false);
		expect(await validate("10-09-2026")).toBe(false);
	});
});
