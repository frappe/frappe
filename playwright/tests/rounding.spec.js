import { test, expect } from "../support";

async function expect_flt(page, rounding_method, cases) {
	const mismatches = await page.evaluate(
		([rounding_method, cases]) =>
			cases
				.map(([value, precision, expected]) => ({
					value,
					precision,
					expected,
					actual: flt(value, precision, null, rounding_method),
				}))
				.filter((d) => d.actual !== d.expected),
		[rounding_method, cases]
	);
	expect(mismatches).toEqual([]);
}

test.describe("Rounding behaviour", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/");
		await desk.ready();
	});

	test("Commercial Rounding", async ({ page }) => {
		await expect_flt(page, "Commercial Rounding", [
			["0.5", 0, 1],
			["0.3", null, 0.3],

			["1.5", 0, 2],

			[0.4, 0, 0],
			[0.5, 0, 1],
			[1.455, 0, 1],
			[1.5, 0, 2],

			[-0.5, 0, -1],
			[-1.5, 0, -2],

			[123, -1, 120],
			[125, -1, 130],
			[134.45, -1, 130],
			[135, -1, 140],

			[1.25, 1, 1.3],
			[0.15, 1, 0.2],
			[2.675, 2, 2.68],

			[-1.25, 1, -1.3],
			[-0.15, 1, -0.2],
		]);
	});

	test("Banker's Rounding", async ({ page }) => {
		const sign_symmetry_cases = [
			[647.325, 647.32],
			[647.315, 647.32],
			[0.125, 0.12],
			[0.135, 0.14],
		].flatMap(([value, expected]) => [
			[value, 2, expected],
			[-value, 2, -expected],
		]);

		await expect_flt(page, "Banker's Rounding", [
			["0.5", 0, 0],
			["0.3", null, 0.3],

			["1.5", 0, 2],

			[0.4, 0, 0],
			[0.5, 0, 0],
			[1.455, 0, 1],
			[1.5, 0, 2],

			[-0.5, 0, 0],
			[-1.5, 0, -2],

			[123, -1, 120],
			[125, -1, 120],
			[134.45, -1, 130],
			[135, -1, 140],

			[1.25, 1, 1.2],
			[0.15, 1, 0.2],
			[2.675, 2, 2.68],
			[-2.675, 2, -2.68],

			[-1.25, 1, -1.2],
			[-0.15, 1, -0.2],

			[0.5, 0, 0],
			[1.5, 0, 2],
			[2.5, 0, 2],
			[3.5, 0, 4],

			[0.05, 1, 0.0],
			[1.15, 1, 1.2],
			[2.25, 1, 2.2],
			[3.35, 1, 3.4],

			[-0.5, 0, 0],
			[-1.5, 0, -2],
			[-2.5, 0, -2],
			[-3.5, 0, -4],

			[-0.05, 1, 0.0],
			[-1.15, 1, -1.2],
			[-2.25, 1, -2.2],
			[-3.35, 1, -3.4],

			...sign_symmetry_cases,
		]);
	});
});
