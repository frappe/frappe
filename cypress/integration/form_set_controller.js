import form_controller_doctype from "../fixtures/form_controller_doctype";
const doctype_name = form_controller_doctype.name;

const controller_script = `
frappe.ui.form.set_controller(
	"${doctype_name}",
	class extends frappe.ui.form.Controller {
		setup() {
			this.frm.set_df_property("mirror", "label", "Set by controller setup");
		}

		title(doc) {
			this.frm.set_value("mirror", doc.title);
		}
	}
);
`;

context("Form Set Controller", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.insert_doc("DocType", form_controller_doctype, true);
		return cy.insert_doc(
			"Client Script",
			{
				__newname: doctype_name,
				dt: doctype_name,
				view: "Form",
				script: controller_script,
				enabled: 1,
			},
			true
		);
	});

	it("binds the controller class while the form loads", () => {
		cy.new_form(doctype_name);
		cy.get('[data-fieldname="mirror"] .control-label').should(
			"contain.text",
			"Set by controller setup"
		);

		cy.fill_field("title", "Mirrored").blur();
		cy.get_field("mirror").should("have.value", "Mirrored");
	});
});
