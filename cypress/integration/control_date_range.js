context("Date Range Control", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	function get_dialog() {
		return cy.dialog({
			title: "Date Range",
			fields: [
				{
					label: "Date Range",
					fieldname: "date_range",
					fieldtype: "Date Range",
				},
			],
		});
	}

	it("Selecting a date range from the datepicker", () => {
		cy.clear_dialogs();
		cy.clear_datepickers();

		get_dialog().as("dialog");
		cy.get_field("date_range", "Date Range").click();
		cy.get(".datepicker--nav-title").click();
		cy.get(".datepicker--nav-title").click({ force: true });

		//Inputing date range values in the date range field
		cy.get(
			".datepicker--years > .datepicker--cells > .datepicker--cell[data-year=2020]"
		).click();
		cy.get(
			".datepicker--months > .datepicker--cells > .datepicker--cell[data-month=0]"
		).click();
		cy.get(".datepicker--cell[data-date=1]:first").click({ force: true });
		cy.get(".datepicker--cell[data-date=15]:first").click({ force: true });

		// Verify if the selected date range values is set in the date range field
		cy.window()
			.its("cur_dialog")
			.then((dialog) => {
				let date_range = dialog.get_value("date_range");
				expect(date_range[0]).to.equal("2020-01-01");
				expect(date_range[1]).to.equal("2020-01-15");
			});
	});
});
