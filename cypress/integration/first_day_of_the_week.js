context("First Day of the Week", () => {
	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/app/system-settings");
		cy.findByText("Date and Number Format").click();
	});

	it("Date control starts with same day as selected in System Settings", () => {
		cy.intercept(
			"POST",
			"/api/method/frappe.core.doctype.system_settings.system_settings.load"
		).as("load_settings");
		cy.fill_field("first_day_of_the_week", "Tuesday", "Select");
		cy.findByRole("button", { name: "Save" }).click();
		cy.wait("@load_settings");
		cy.dialog({
			title: "Date",
			fields: [
				{
					label: "Date",
					fieldname: "date",
					fieldtype: "Date",
				},
			],
		});
		cy.get_field("date").click();
		cy.get(".datepicker--day-name").eq(0).should("have.text", "Tu");
	});

	it("Calendar view starts with same day as selected in System Settings", () => {
		cy.intercept(
			"POST",
			"/api/method/frappe.core.doctype.system_settings.system_settings.load"
		).as("load_settings");
		cy.fill_field("first_day_of_the_week", "Monday", "Select");
		cy.findByRole("button", { name: "Save" }).click();
		cy.wait("@load_settings");
		cy.visit("app/todo/view/calendar/default");
		cy.get(".fc-day-header > span").eq(0).should("have.text", "Mon");
	});

	after(() => {
		cy.visit("/app/system-settings");
		cy.findByText("Date and Number Format").click();
		cy.fill_field("first_day_of_the_week", "Sunday", "Select");
		cy.findByRole("button", { name: "Save" }).click();
	});
});
