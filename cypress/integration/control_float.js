context("Control Float", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
	});

	function get_dialog_with_float() {
		return cy.dialog({
			title: "Float Check",
			animate: false,
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
		cy.wait(300);

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
				cy.wait(100);
				cy.get_field("float_number", "Float").focus();
				cy.wait(100);
				cy.get_field("float_number", "Float").blur();
				cy.wait(100);
				cy.get_field("float_number", "Float").focus();
				cy.wait(100);
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
						focus_expected: "36.487,334",
					},
					{
						input: "36487,335",
						blur_expected: "36.487,335",
						focus_expected: "36.487,335",
					},
					{
						input: "2*(2+47)+1,5+1",
						blur_expected: "100,500",
						focus_expected: "100,500",
					},
				],
			},
			{
				number_format: "#,###.##",
				values: [
					{
						input: "464,87.334",
						blur_expected: "46,487.334",
						focus_expected: "46,487.334",
					},
					{
						input: "46487.335",
						blur_expected: "46,487.335",
						focus_expected: "46,487.335",
					},
					{
						input: "3*(2+47)+1.5+1",
						blur_expected: "149.500",
						focus_expected: "149.500",
					},
				],
			},
			{
				// '.' is the parseFloat's decimal separator
				number_format: "#.###,##",
				values: [
					{
						input: "12.345",
						blur_expected: "12.345,000",
						focus_expected: "12.345,000",
					},
					{
						// parseFloat would reduce 12,340 to 12,34 if this string was ever to be parsed
						input: "12.340",
						blur_expected: "12.340,000",
						focus_expected: "12.340,000",
					},
				],
			},
		];
	}
});
