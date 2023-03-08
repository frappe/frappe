context("Rounding behaviour", () => {
	before(() => {
		cy.login();
		cy.visit("/app/");
	});

	it("Rounds floats accurately", () => {
		cy.window()
			.its("flt")
			.then((flt) => {
				let rounding_method = "Rounding Half Away From Zero";

				expect(flt("0.5", 0, null, rounding_method)).eq(1);
				expect(flt("0.3", null, null, rounding_method)).eq(0.3);

				expect(flt("1.5", 0, null, rounding_method)).eq(2);

				// positive rounding to integers
				expect(flt(0.4, 0, null, rounding_method)).eq(0);
				expect(flt(0.5, 0, null, rounding_method)).eq(1);
				expect(flt(1.455, 0, null, rounding_method)).eq(1);
				expect(flt(1.5, 0, null, rounding_method)).eq(2);

				// negative rounding to integers
				expect(flt(-0.5, 0, null, rounding_method)).eq(-1);
				expect(flt(-1.5, 0, null, rounding_method)).eq(-2);

				// negative precision i.e. round to nearest 10th
				expect(flt(123, -1, null, rounding_method)).eq(120);
				expect(flt(125, -1, null, rounding_method)).eq(130);
				expect(flt(134.45, -1, null, rounding_method)).eq(130);
				expect(flt(135, -1, null, rounding_method)).eq(140);

				//  positive multiple digit rounding
				expect(flt(1.25, 1, null, rounding_method)).eq(1.3);
				expect(flt(0.15, 1, null, rounding_method)).eq(0.2);
				expect(flt(2.675, 2, null, rounding_method)).eq(2.68);

				//  negative multiple digit rounding
				expect(flt(-1.25, 1, null, rounding_method)).eq(-1.3);
				expect(flt(-0.15, 1, null, rounding_method)).eq(-0.2);
			});
	});
});
