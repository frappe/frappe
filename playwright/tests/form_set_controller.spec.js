import { test, expect } from "../support";
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

function insert_client_script(admin, dt, script) {
	return admin.insert_doc(
		"Client Script",
		{ __newname: dt, dt: dt, view: "Form", script: script, enabled: 1 },
		true
	);
}

test.describe("Form Set Controller", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", form_controller_doctype, true);
		await admin.insert_doc(
			"DocType",
			{ ...form_controller_doctype, name: subclass_doctype_name },
			true
		);
		await insert_client_script(admin, doctype_name, controller_script);
		await insert_client_script(admin, subclass_doctype_name, subclass_script);
	});

	test("binds the controller class while the form loads", async ({ page, desk }) => {
		await desk.new_form(doctype_name);
		await expect(page.locator('[data-fieldname="mirror"] .control-label')).toContainText(
			"Set by controller setup"
		);

		const title = await desk.fill_field("title", "Mirrored");
		await title.blur();
		await expect(desk.get_field("mirror")).toHaveValue("Mirrored");
	});

	test("keeps a subclass that a form script already bound", async ({ page, desk }) => {
		await desk.new_form(subclass_doctype_name);
		const title = await desk.fill_field("title", "Mirrored");
		await title.blur();
		await expect(desk.get_field("mirror")).toHaveValue("Mirrored");
	});
});
