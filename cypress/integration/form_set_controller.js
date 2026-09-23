import form_controller_doctype from "../fixtures/form_controller_doctype";
const doctype_name = form_controller_doctype.name;
const subclass_doctype_name = "Form Controller Subclass Test";

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

const subclass_script = `
class Base extends frappe.ui.form.Controller {
	title() {
		this.frm.set_value("mirror", "Set by the registered class");
	}
}

class Subclass extends Base {
	title(doc) {
		this.frm.set_value("mirror", doc.title);
	}
}

frappe.ui.form.set_controller("${subclass_doctype_name}", Base);
extend_cscript(cur_frm.cscript, new Subclass({ frm: cur_frm }));
`;

function insert_client_script(dt, script) {
	return cy.insert_doc(
		"Client Script",
		{ __newname: dt, dt: dt, view: "Form", script: script, enabled: 1 },
		true
	);
}

context("Form Set Controller", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.insert_doc("DocType", form_controller_doctype, true);
		cy.insert_doc(
			"DocType",
			{ ...form_controller_doctype, name: subclass_doctype_name },
			true
		);
		insert_client_script(doctype_name, controller_script);
		return insert_client_script(subclass_doctype_name, subclass_script);
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

	it("keeps a subclass that a form script already bound", () => {
		cy.new_form(subclass_doctype_name);
		cy.fill_field("title", "Mirrored").blur();
		cy.get_field("mirror").should("have.value", "Mirrored");
	});
});
