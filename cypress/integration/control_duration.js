context("Control Duration", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
	});

	afterEach(() => {
		cy.clear_dialogs();
	});

	function get_dialog_with_duration(hide_days = 0, hide_seconds = 0) {
		return cy.dialog({
			title: "Duration",
			fields: [
				{
					fieldname: "duration",
					fieldtype: "Duration",
					hide_days: hide_days,
					hide_seconds: hide_seconds,
				},
			],
		});
	}

	it("should set duration", () => {
		get_dialog_with_duration().as("dialog");
		cy.get(".frappe-control[data-fieldname=duration] input").first().click();
		cy.get(".duration-input[data-duration=days]")
			.type(45, { force: true })
			.blur({ force: true });
		cy.get(".duration-input[data-duration=seconds]").type(5400).blur({ force: true });
		cy.get(".frappe-control[data-fieldname=duration] input")
			.first()
			.should("have.value", "6w 3d 1h 30min");
		cy.get(".frappe-control[data-fieldname=duration] input").first().blur();
		cy.get(".duration-picker").should("not.be.visible");
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("duration");
			expect(value).to.equal(3893400);
		});
	});

	it("should hide units as configured and convert to the next higher unit", () => {
		get_dialog_with_duration(1, 1).as("dialog");
		cy.get(".frappe-control[data-fieldname=duration] input").first();
		cy.get(".duration-input[data-duration=days]").should("not.be.visible");
		cy.get(".duration-input[data-duration=seconds]").should("not.be.visible");
		cy.get(".duration-input[data-duration=hours]").type(342);
		cy.get(".duration-input[data-duration=hours]").blur();
		cy.get(".frappe-control[data-fieldname=duration] input")
			.first()
			.should("have.value", "2w 6h");
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("duration");
			expect(value).to.equal(1231200);
		});
	});
});
