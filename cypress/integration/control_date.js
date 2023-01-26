context("Date Control", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	function get_dialog(date_field_options) {
		return cy.dialog({
			title: "Date",
			fields: [
				{
					label: "Date",
					fieldname: "date",
					fieldtype: "Date",
					in_list_view: 1,
					...date_field_options,
				},
			],
		});
	}

	it("Selecting a date from the datepicker & check prev & next button", () => {
		cy.clear_dialogs();
		cy.clear_datepickers();

		get_dialog().as("dialog");
		cy.get_field("date", "Date").click();
		cy.get(".datepicker--nav-title").click();
		cy.get(".datepicker--nav-title").click({ force: true });

		//Inputing values in the date field
		cy.get(
			".datepicker--years > .datepicker--cells > .datepicker--cell[data-year=2020]"
		).click();
		cy.get(
			".datepicker--months > .datepicker--cells > .datepicker--cell[data-month=0]"
		).click();
		cy.get(".datepicker--days > .datepicker--cells > .datepicker--cell[data-date=15]").click();

		// Verify if the selected date is set the date field
		cy.window().its("cur_dialog.fields_dict.date.value").should("be.equal", "2020-01-15");

		cy.get_field("date", "Date").click();

		//Clicking on the next button in the datepicker
		cy.get(".datepicker--nav-action[data-action=next]").click();

		//Selecting a date from the datepicker
		cy.get(".datepicker--cell[data-date=15]").click({ force: true });

		//Verifying if the selected date has been displayed in the date field
		cy.window().its("cur_dialog.fields_dict.date.value").should("be.equal", "2020-02-15");
		cy.wait(500);
		cy.get_field("date", "Date").click();

		//Clicking on the previous button in the datepicker
		cy.get(".datepicker--nav-action[data-action=prev]").click();

		//Selecting a date from the datepicker
		cy.get(".datepicker--cell[data-date=15]").click({ force: true });

		//Verifying if the selected date has been displayed in the date field
		cy.window().its("cur_dialog.fields_dict.date.value").should("be.equal", "2020-01-15");
	});

	it('Clicking on "Today" button gives todays date', () => {
		cy.clear_dialogs();
		cy.clear_datepickers();

		get_dialog().as("dialog");
		cy.get_field("date", "Date").click();

		//Clicking on "Today" button
		cy.get(".datepicker--button").click();

		//Verifying if clicking on "Today" button matches today's date
		cy.window().then((win) => {
			expect(win.cur_dialog.fields_dict.date.value).to.be.equal(
				win.frappe.datetime.get_today()
			);
		});
	});
});
