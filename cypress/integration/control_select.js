context("Control Select", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
	});

	function get_dialog_with_select() {
		return cy.dialog({
			title: "Select",
			fields: [
				{
					fieldname: "select_control",
					fieldtype: "Select",
					placeholder: "Select an Option",
					options: ["", "Option 1", "Option 2", "Option 2"],
				},
			],
		});
	}

	it("toggles placholder on clicking an option", () => {
		get_dialog_with_select().as("dialog");

		cy.get(".frappe-control[data-fieldname=select_control] .control-input").as("control");
		cy.get(".frappe-control[data-fieldname=select_control] .control-input select").as(
			"select"
		);
		cy.get("@control").get(".select-icon").should("exist");
		cy.get("@control").get(".placeholder").should("have.css", "display", "block");
		cy.get("@select").select("Option 1");
		cy.findByDisplayValue("Option 1").should("exist");
		cy.get("@control").get(".placeholder").should("have.css", "display", "none");
		cy.get("@select").invoke("val", "");
		cy.findByDisplayValue("Option 1").should("not.exist");
		cy.get("@control").get(".placeholder").should("have.css", "display", "block");

		cy.get("@dialog").then((dialog) => {
			dialog.hide();
		});
	});
});
