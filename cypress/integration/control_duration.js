context("Control Duration", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	beforeEach(() => {
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
		cy.wait(500);
		cy.get(".frappe-control[data-fieldname=duration] input").first().click();
		cy.get(".duration-input[data-duration=days]")
			.type(45, { force: true })
			.blur({ force: true });
		cy.wait(500);
		cy.get(".duration-input[data-duration=minutes]").type(30).blur({ force: true });
		cy.wait(500);
		cy.get(".frappe-control[data-fieldname=duration] input")
			.first()
			.should("have.value", "45d 30m");
		cy.get(".frappe-control[data-fieldname=duration] input").first().blur();
		// Picker is detached from <body> on hide (not just display:none),
		// so assert it's absent from the DOM rather than merely hidden.
		cy.get(".duration-picker").should("not.exist");
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("duration");
			expect(value).to.equal(3889800);
			cy.hide_dialog();
		});
	});

	it("should hide days or seconds according to duration options", () => {
		get_dialog_with_duration(1, 1).as("dialog");
		// Focus the input so the picker mounts to <body> — otherwise the
		// .duration-input children don't exist yet (picker is detached until shown).
		cy.get(".frappe-control[data-fieldname=duration] input").first().focus();
		cy.wait(500);
		cy.get(".duration-input[data-duration=days]").should("not.be.visible");
		cy.get(".duration-input[data-duration=seconds]").should("not.be.visible");
	});
});
