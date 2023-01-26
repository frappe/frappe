context("Control Float", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
	});

	function get_dialog_with_float() {
		return cy.dialog({
			title: "Float Check",
			fields: [
				{
					fieldname: "float_number",
					fieldtype: "Float",
					Label: "Float",
				},
			],
		});
	}

	it("check value changes", () => {
		get_dialog_with_float().as("dialog");

		let data = get_data();
		data.forEach((x) => {
			cy.window()
				.its("frappe")
				.then((frappe) => {
					frappe.boot.sysdefaults.number_format = x.number_format;
				});
			x.values.forEach((d) => {
				cy.get_field("float_number", "Float").clear();
				cy.wait(200);
				cy.fill_field("float_number", d.input, "Float").blur();
				cy.get_field("float_number", "Float").should("have.value", d.blur_expected);

				cy.get_field("float_number", "Float").focus();
				cy.get_field("float_number", "Float").blur();
				cy.get_field("float_number", "Float").focus();
				cy.get_field("float_number", "Float").should("have.value", d.focus_expected);
			});
		});
	});

	function get_data() {
		return [
			{
				number_format: "#.###,##",
				values: [
					{
						input: "364.87,334",
						blur_expected: "36.487,334",
						focus_expected: "36487.334",
					},
					{
						input: "36487,334",
						blur_expected: "36.487,334",
						focus_expected: "36487.334",
					},
					{
						input: "100",
						blur_expected: "100,000",
						focus_expected: "100",
					},
				],
			},
			{
				number_format: "#,###.##",
				values: [
					{
						input: "364,87.334",
						blur_expected: "36,487.334",
						focus_expected: "36487.334",
					},
					{
						input: "36487.334",
						blur_expected: "36,487.334",
						focus_expected: "36487.334",
					},
					{
						input: "100",
						blur_expected: "100.000",
						focus_expected: "100",
					},
				],
			},
		];
	}
});
