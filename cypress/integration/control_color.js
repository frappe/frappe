context("Control Color", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
	});

	function get_dialog_with_color() {
		return cy.dialog({
			title: "Color",
			fields: [
				{
					label: "Color",
					fieldname: "color",
					fieldtype: "Color",
				},
			],
		});
	}

	it("Verifying if the color control is selecting correct", () => {
		get_dialog_with_color().as("dialog");
		cy.findByPlaceholderText("Choose a color").click();

		///Selecting a color from the color palette
		cy.get('[style="background-color: rgb(79, 157, 217);"]').click();

		//Checking if the css attribute is correct
		cy.get(".color-map").should("have.css", "color", "rgb(79, 157, 217)");
		cy.get(".hue-map").should("have.css", "color", "rgb(0, 145, 255)");

		//Checking if the correct color is being selected
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("color");
			expect(value).to.equal("#4F9DD9");
		});

		//Selecting a color
		cy.get('[style="background-color: rgb(203, 41, 41);"]').click();

		//Checking if the correct css is being selected
		cy.get(".color-map").should("have.css", "color", "rgb(203, 41, 41)");
		cy.get(".hue-map").should("have.css", "color", "rgb(255, 0, 0)");

		//Checking if the correct color is being selected
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("color");
			expect(value).to.equal("#CB2929");
		});

		//Selecting color from the palette
		cy.get(".color-map > .color-selector").click(65, 87, { force: true });
		cy.get(".color-map").should("have.css", "color", "rgb(56, 0, 0)");

		//Checking if the expected color is selected and getting displayed
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("color");
			expect(value).to.equal("#380000");
		});

		//Selecting the color from the hue map
		cy.get(".hue-map > .hue-selector").click(35, -1, { force: true });
		cy.get(".color-map").should("have.css", "color", "rgb(56, 45, 0)");
		cy.get(".hue-map").should("have.css", "color", "rgb(255, 204, 0)");
		cy.get(".color-map > .color-selector").click(55, 12, { force: true });
		cy.get(".color-map").should("have.css", "color", "rgb(46, 37, 0)");

		//Checking if the correct color is being displayed
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("color");
			expect(value).to.equal("#2e2500");
		});

		//Clearing the field and checking if the field contains the placeholder "Choose a color"
		cy.get(".input-with-feedback").click({ force: true });
		cy.get_field("color", "Color").type("{selectall}").clear();
		cy.get_field("color", "Color")
			.invoke("attr", "placeholder")
			.should("contain", "Choose a color");
	});
});
