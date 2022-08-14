const test_button_names = [
	"Metallica",
	"Pink Floyd",
	"Porcupine Tree (the GOAT)",
	"AC / DC",
	`Electronic Dance "music"`,
	"l'imperatrice",
];

const add_button = (label, group = "TestGroup") => {
	cy.window()
		.its("cur_frm")
		.then((frm) => {
			frm.add_custom_button(label, () => {}, group);
		});
};

const check_button_count = (label, group = "TestGroup") => {
	// Verify main buttons
	cy.findByRole("button", { name: group }).click();
	cy.get(`[data-label="${encodeURIComponent(label)}"]`)
		.should("have.length", 1)
		.should("be.visible");

	// Verify dropdown buttons in mobile view
	cy.viewport(420, 900);
	const dropdown_btn_label = `${group} > ${label}`;
	cy.get(".menu-btn-group > .btn").click();
	cy.get(`[data-label="${encodeURIComponent(dropdown_btn_label)}"]`)
		.should("have.length", 1)
		.should("be.visible");

	//reset viewport
	cy.viewport(Cypress.config("viewportWidth"), Cypress.config("viewportHeight"));
};

describe(
	"Custom group button behaviour on desk",
	{ scrollBehavior: false }, // speeds up the test
	() => {
		before(() => {
			cy.login();
			cy.visit(`/app/note/new`);
		});

		test_button_names.forEach((button_name) => {
			it(`Custom button works with name '${button_name}'`, () => {
				add_button(button_name);
				check_button_count(button_name);

				// duplicate button shouldn't be added
				add_button(button_name);
				check_button_count(button_name);
			});
		});
	}
);
