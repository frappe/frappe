context("Form Intro", () => {
	before(() => {
		cy.login();
	});

	it("keeps a single intro message after the first save of a new document", () => {
		cy.new_form("ToDo");

		cy.window().then((win) => {
			win.frappe.ui.form.on("ToDo", {
				refresh(frm) {
					frm.set_intro("Intro set from refresh", "blue");
				},
			});
			win.cur_frm.refresh();
		});

		cy.get(".form-message").should("have.length", 1);

		cy.fill_field("description", "test intro dedupe", "Text Editor").blur().wait(200);
		cy.save();

		// first save renames the new document and reroutes to it; wait for that to land
		cy.get("body").should(($body) => {
			expect($body.attr("data-route")).to.not.match(/\/new-todo-/);
		});
		cy.wait(300);

		cy.get(".form-message").should("have.length", 1);
	});
});
