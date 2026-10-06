import { test, expect } from "../support";

test.describe("Utils", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk");
		await desk.ready();
	});

	function run_util(page, name, ...args) {
		return page.evaluate(([name, args]) => frappe.utils[name](...args), [name, args]);
	}

	test("should round hidden seconds to minutes", async ({ page }) => {
		expect(await run_util(page, "seconds_to_duration", 89, { hide_seconds: 1 })).toEqual({
			days: 0,
			hours: 0,
			minutes: 1,
			seconds: 0,
		});

		expect(await run_util(page, "seconds_to_duration", -89, { hide_seconds: 1 })).toEqual({
			days: -0,
			hours: -0,
			minutes: -1,
			seconds: 0,
		});

		expect(await run_util(page, "seconds_to_duration", 91, { hide_seconds: 1 })).toEqual({
			days: 0,
			hours: 0,
			minutes: 2,
			seconds: 0,
		});

		expect(await run_util(page, "seconds_to_duration", -91, { hide_seconds: 1 })).toEqual({
			days: -0,
			hours: -0,
			minutes: -2,
			seconds: 0,
		});

		expect(await run_util(page, "seconds_to_duration", 60 * 60, { hide_seconds: 1 })).toEqual({
			days: 0,
			hours: 1,
			minutes: 0,
			seconds: 0,
		});

		expect(await run_util(page, "seconds_to_duration", 15 * 60, { hide_seconds: 1 })).toEqual({
			days: 0,
			hours: 0,
			minutes: 15,
			seconds: 0,
		});
	});

	test("should escape the docname when it is used as the link text", async ({ page }) => {
		const link = await run_util(
			page,
			"get_form_link",
			"ToDo",
			"<img src=x onerror=alert(1)>",
			true
		);
		expect(link).toBe(
			'<a href="/desk/todo/%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E">' +
				"&lt;img src&#x3D;x onerror&#x3D;alert(1)&gt;</a>"
		);
	});

	test("should not escape display text passed by the caller", async ({ page }) => {
		const link = await run_util(
			page,
			"get_form_link",
			"ToDo",
			"TODO-0001",
			true,
			"<b>Open item</b>"
		);
		expect(link).toBe('<a href="/desk/todo/TODO-0001"><b>Open item</b></a>');
	});

	test("should keep zero when shortening a number", async ({ page }) => {
		expect(await run_util(page, "shorten_number", 0)).toBe("0");
	});

	test("should parse days, hours, minutes and seconds", async ({ page }) => {
		const seconds = 60 * 60 * 24 + 60 * 60 + 60 + 1;

		expect(await run_util(page, "seconds_to_duration", seconds)).toEqual({
			days: 1,
			hours: 1,
			minutes: 1,
			seconds: 1,
		});

		expect(await run_util(page, "seconds_to_duration", seconds * -1)).toEqual({
			days: -1,
			hours: -1,
			minutes: -1,
			seconds: -1,
		});

		expect(
			await run_util(page, "seconds_to_duration", seconds, {
				hide_days: 1,
				hide_seconds: 1,
			})
		).toEqual({
			days: 0,
			hours: 25,
			minutes: 1,
			seconds: 0,
		});

		expect(
			await run_util(page, "seconds_to_duration", seconds * -1, {
				hide_days: 1,
				hide_seconds: 1,
			})
		).toEqual({
			days: 0,
			hours: -25,
			minutes: -1,
			seconds: 0,
		});
	});
});
