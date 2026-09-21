import web_form_source_doctype from "../fixtures/web_form_source_doctype";
import web_form_empty_source_doctype from "../fixtures/web_form_empty_source_doctype";
import {
	CANVAS,
	ROUTE,
	SINGLE_PAGE_FIELDS,
	fill_new_web_form,
	open_get_fields,
	seed_web_form,
	web_form_fields,
} from "../support/web_form";

const SOURCE_ROUTE = "source-note";
const SOURCE_DOCTYPE = "Web Form Source";
const EMPTY_ROUTE = "empty-source-note";

// every field the picker can offer from the seeded DocType, in its own field order
const OFFERED = [
	"title",
	"kind",
	"alpha_note",
	"bare_note",
	"bracket_note",
	"scripted_note",
	"flagged",
	"roles",
];

// a Web Form is named after its scrubbed title, so passing the route as the title keeps
// the name and the route the same and the desk URL predictable
function seed_source_web_form(fields = [], doc_type = SOURCE_DOCTYPE, route = SOURCE_ROUTE) {
	cy.remove_doc("Web Form", route, true);
	return cy.insert_doc(
		"Web Form",
		{
			title: route,
			route: route,
			doc_type: doc_type,
			module: "Website",
			web_form_fields: fields,
		},
		true
	);
}

// the picker's own dialog, not whatever modal happens to be open
function picker() {
	return cy.get_open_dialog().filter(':contains("Get Fields from")');
}

function open_picker_on(fields = []) {
	seed_source_web_form(fields);
	return open_get_fields(SOURCE_ROUTE);
}

function set_update_type(label) {
	picker().find('[data-fieldname="update_type"] select').select(label);
}

function check_only(fieldnames) {
	picker().find('[data-action="unselect_all"]').click();
	fieldnames.forEach((fieldname) =>
		picker().find(`:checkbox[data-unit='${fieldname}']`).check()
	);
}

function row_for(fields, fieldname) {
	return fields.find((d) => d.fieldname === fieldname);
}

// a dropped condition is simply absent, and the grid reads that back as null or ""
function expect_no_condition(fields, fieldname, key) {
	expect(row_for(fields, fieldname)[key], `${fieldname}.${key}`).to.be.oneOf([
		null,
		undefined,
		"",
	]);
}

// A row only goes stale without a save, so it cannot be seeded: the server rejects a row
// naming a field its doctype does not have. Point the form at ToDo in the UI instead, which
// shares no field with either source doctype, and every seeded row is left over.
function open_picker_on_leftover_rows(seed) {
	seed();
	// Get Fields flushes the builder first, so let it mount before the switch
	cy.get(CANVAS).should("exist");

	cy.fill_field("doc_type", "ToDo", "Link");
	cy.click_custom_action_button("Get Fields");
	return picker();
}

function seed_source_and_open(fields) {
	seed_source_web_form(fields);
	cy.visit(`/desk/web-form/${SOURCE_ROUTE}`);
}

function seed_note_and_open() {
	seed_web_form(SINGLE_PAGE_FIELDS);
	cy.visit(`/desk/web-form/${ROUTE}`);
}

context("Web Form Get Fields", () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
		cy.insert_doc("DocType", web_form_source_doctype, true);
		cy.insert_doc("DocType", web_form_empty_source_doctype, true);
	});

	it("Offers every field a Web Form can render", () => {
		open_picker_on();

		OFFERED.forEach((fieldname) => {
			// Table MultiSelect only reaches the list when the fieldtype is spelled its way
			picker().find(`:checkbox[data-unit='${fieldname}']`).should("exist");
		});

		// a Button carries no value, and a hidden field cannot be filled in
		picker().find(":checkbox[data-unit='run_action']").should("not.exist");
		picker().find(":checkbox[data-unit='secret_note']").should("not.exist");
	});

	it("Marks the mandatory fields and preselects them on an empty form", () => {
		open_picker_on();

		picker().find(".label-area[data-unit='title'] .text-danger").should("exist");
		picker().find(".label-area[data-unit='kind'] .text-danger").should("not.exist");

		// nothing has been removed on purpose yet, so mandatory fields start ticked
		picker().find(":checkbox[data-unit='title']").should("be.checked");
		picker().find(":checkbox[data-unit='kind']").should("not.be.checked");
	});

	it("Names the condition a field carries", () => {
		open_picker_on();

		picker()
			.find(".label-area[data-unit='alpha_note'] .multicheck-warning-icon")
			// bootstrap moves `title` aside once the tooltip is initialised
			.should("have.attr", "data-original-title")
			.and("contain", "Depends on: eval:doc.kind == 'Alpha'");

		// all three keys are listed, so the author sees every condition the field carries
		picker()
			.find(".label-area[data-unit='flagged'] .multicheck-warning-icon")
			.should("have.attr", "data-original-title")
			.and("contain", "eval:doc.kind == 'Beta', eval:doc.kind == 'Alpha'");

		picker()
			.find(".label-area[data-unit='kind'] .multicheck-warning-icon")
			.should("not.exist");
	});

	it("Lists a repeated condition once", () => {
		seed_source_and_open();
		cy.get(CANVAS).should("exist");

		// the two keys often hold the same expression, and naming it twice reads as a bug
		cy.window().then((win) => {
			const df = win.frappe.meta.get_docfield(SOURCE_DOCTYPE, "flagged");
			df.read_only_depends_on = df.mandatory_depends_on;
		});
		cy.click_custom_action_button("Get Fields");

		picker()
			.find(".label-area[data-unit='flagged'] .multicheck-warning-icon")
			.should("have.attr", "data-original-title")
			.and("eq", "Depends on: eval:doc.kind == 'Beta'");
	});

	it("Describes what each update type does", () => {
		open_picker_on();

		// nothing to lose on an empty form, so the destructive rebuild is the default
		picker()
			.find('[data-fieldname="update_type"] .help-box')
			.should("contain.text", "doctype order");

		set_update_type("Fields Only");
		picker()
			.find('[data-fieldname="update_type"] .help-box')
			.should("contain.text", "appended");
	});

	it("Defaults to appending once the form has fields of its own", () => {
		open_picker_on([{ fieldname: "kind", fieldtype: "Select", label: "Kind" }]);

		picker()
			.find('[data-fieldname="update_type"] select')
			.should("have.value", "add_and_remove");
	});

	it("Filters the list without resizing it", () => {
		open_picker_on();

		picker()
			.find('[data-fieldname="fields"]')
			.then(($wrapper) => {
				const height = $wrapper.height();

				picker().find('[data-element="search"]').type("alpha");

				picker()
					.find(".unit-checkbox:has(.label-area[data-unit='alpha_note'])")
					.should("be.visible");
				picker()
					.find(".unit-checkbox:has(.label-area[data-unit='title'])")
					.should("not.be.visible");
				// the list is frozen, or it would shrink onto the search box on every keystroke
				picker()
					.find('[data-fieldname="fields"]')
					.should(($after) => {
						expect($after.height(), "list height while filtering").to.eq(height);
					});
			});
	});

	it("Ticks and unticks the whole list", () => {
		open_picker_on();

		picker().find('[data-action="unselect_all"]').click();
		picker().find(":checkbox:checked").should("not.exist");

		picker().find('[data-action="select_all"]').click();
		picker().find(":checkbox:not(:checked)").should("not.exist");
	});

	it("Select Mandatory adds to the selection instead of replacing it", () => {
		// a form with fields, so the picker does not tick the mandatory ones by itself
		open_picker_on([{ fieldname: "kind", fieldtype: "Select", label: "Kind" }]);

		picker().find(":checkbox[data-unit='title']").should("not.be.checked");

		picker().find('[data-action="select_mandatory"]').click();

		picker().find(":checkbox[data-unit='title']").should("be.checked");
		// an untick deletes that row on Update, so this button never unticks
		picker().find(":checkbox[data-unit='kind']").should("be.checked");
	});

	it("Escapes a label that carries markup", () => {
		open_picker_on([{ fieldname: "kind", fieldtype: "Select", label: "<b>Kind</b>" }]);

		picker().find(".label-area[data-unit='kind']").should("contain.text", "<b>Kind</b>");
		picker().find(".label-area[data-unit='kind'] b").should("not.exist");
	});

	it("Falls back to the fieldname when nothing carries a label", () => {
		// neither the row nor any docfield names it once the form points at ToDo
		open_picker_on_leftover_rows(() =>
			seed_source_and_open([{ fieldname: "kind", fieldtype: "Select" }])
		);

		picker().find(".label-area[data-unit='kind']").should("contain.text", "Kind");
	});

	it("Explains a row the picker can no longer add", () => {
		open_picker_on([
			{ fieldname: "secret_note", fieldtype: "Data", label: "Secret Note" },
			{ fieldname: "run_action", fieldtype: "Data", label: "Run Action" },
		]);

		// both still name a field of the doctype, so neither reads as "not a field"
		picker()
			.find(".label-area[data-unit='secret_note']")
			.should("have.class", "text-muted")
			.find(".multicheck-warning-icon")
			.should("have.attr", "data-original-title")
			.and("contain", "Hidden in Web Form Source");

		picker()
			.find(".label-area[data-unit='run_action']")
			.should("have.class", "text-muted")
			.find(".multicheck-warning-icon")
			.should("have.attr", "data-original-title")
			.and("contain", "cannot show this Button field");

		// still ticked, so Update keeps them until they are unticked
		picker().find(":checkbox[data-unit='secret_note']").should("be.checked");
	});

	it("Drops a condition when the fields it reads are left out", () => {
		open_picker_on();

		// `kind` stays unticked, so nothing that reads it can be evaluated on the portal
		check_only(["alpha_note", "bare_note", "bracket_note", "scripted_note", "flagged"]);
		cy.click_modal_primary_button("Update");

		web_form_fields().should((fields) => {
			expect_no_condition(fields, "alpha_note", "depends_on");
			expect_no_condition(fields, "bare_note", "depends_on");
			expect_no_condition(fields, "bracket_note", "depends_on");
			expect_no_condition(fields, "flagged", "mandatory_depends_on");
			expect_no_condition(fields, "flagged", "read_only_depends_on");
		});
	});

	it("Carries a condition over when the field it reads is added too", () => {
		open_picker_on();

		picker().find('[data-action="select_all"]').click();
		cy.click_modal_primary_button("Update");

		web_form_fields().should((fields) => {
			expect(row_for(fields, "alpha_note").depends_on).to.eq("eval:doc.kind == 'Alpha'");
			expect(row_for(fields, "bare_note").depends_on).to.eq("kind");
			// the bracket accessor names the same field as the dotted one
			expect(row_for(fields, "bracket_note").depends_on).to.eq(
				"eval:doc['kind'] == 'Alpha'"
			);
			expect(row_for(fields, "flagged").mandatory_depends_on).to.eq(
				"eval:doc.kind == 'Beta'"
			);
			expect(row_for(fields, "flagged").read_only_depends_on).to.eq(
				"eval:doc.kind == 'Alpha'"
			);
			// a Desk form script method has nothing to run against on the portal
			expect_no_condition(fields, "scripted_note", "depends_on");
		});
	});

	it("Rebuilds the layout in doctype order", () => {
		open_picker_on();

		picker().find('[data-action="select_all"]').click();
		cy.click_modal_primary_button("Update");

		web_form_fields().should((fields) => {
			const placed = fields.filter((d) => d.fieldname).map((d) => d.fieldname);
			expect(placed).to.deep.eq(OFFERED);
		});

		// not scroll_to_field: the update lands the author on the canvas it just rebuilt
		cy.get(CANVAS).should("be.visible");
	});

	it("Keeps the fields already on the form when it appends", () => {
		open_picker_on([{ fieldname: "kind", fieldtype: "Select", label: "Custom Kind Label" }]);

		picker().find('[data-action="select_all"]').click();
		cy.click_modal_primary_button("Update");

		web_form_fields().should((fields) => {
			// the row is reused, so a label edited on the form survives the update
			expect(row_for(fields, "kind").label).to.eq("Custom Kind Label");
			// and appending leaves it where it was
			expect(fields[0].fieldname).to.eq("kind");
			expect(fields.map((d) => d.fieldname)).to.include("title");
		});
	});

	it("Removes the unticked rows and marks the form unsaved", () => {
		open_picker_on([
			{ fieldname: "kind", fieldtype: "Select", label: "Kind" },
			{ fieldname: "title", fieldtype: "Data", label: "Title" },
		]);

		picker().find(":checkbox[data-unit='kind']").uncheck();
		cy.click_modal_primary_button("Update");

		web_form_fields().should((fields) => {
			expect(fields.map((d) => d.fieldname)).to.not.include("kind");
			// clear_doc renumbers, so the rows that stay are still 1..n
			expect(fields.map((d) => d.idx)).to.deep.eq(fields.map((_, i) => i + 1));
		});
		// clear_doc does not dirty the form by itself
		cy.get('[data-testid="page-status"]').should("contain.text", "Not Saved");
	});

	it("Saves a web form left with no fields", () => {
		open_picker_on([{ fieldname: "kind", fieldtype: "Select", label: "Kind" }]);

		picker().find('[data-action="unselect_all"]').click();
		cy.click_modal_primary_button("Update");

		web_form_fields().should("have.length", 0);

		// a field-less web form renders blank rather than blocking the author
		cy.click_doc_primary_button("Save");
		cy.get('[data-testid="page-status"]').should("not.contain.text", "Not Saved");
		web_form_fields().should("have.length", 0);
	});

	it("Says when a doctype has no fields to offer", () => {
		seed_source_web_form([], "Web Form Empty Source", EMPTY_ROUTE);
		cy.visit(`/desk/web-form/${EMPTY_ROUTE}`);
		cy.get(CANVAS).should("exist");

		cy.click_custom_action_button("Get Fields");

		cy.get(".msgprint").should(
			"contain.text",
			"No fields are available from Web Form Empty Source"
		);
		cy.get_open_dialog().should("not.contain.text", "Get Fields from");
	});

	it("Get Fields survives the first save", () => {
		// the builder mounts with an empty grid, and must not write that back over Get Fields
		fill_new_web_form("Builder Note New");

		web_form_fields().then((collected) => {
			cy.save();
			web_form_fields().should("have.length", collected.length);
		});
	});

	it("Marks the fields left over from the previous DocType", () => {
		open_picker_on_leftover_rows(seed_note_and_open);

		picker().within(() => {
			// still selected, so Update keeps it until it is unselected
			cy.get(":checkbox[data-unit='title']").should("be.checked");
			cy.get(".label-area[data-unit='title']")
				.should("have.class", "text-muted")
				.find(".multicheck-warning-icon")
				.should("have.attr", "data-original-title")
				.and("contain", "Not a field in ToDo");

			// a real ToDo field is left alone
			cy.get(".label-area[data-unit='description']")
				.should("not.have.class", "text-muted")
				.find(".multicheck-warning-icon")
				.should("not.exist");
		});
	});

	it("Removes a field left over from the previous DocType when it is unselected", () => {
		open_picker_on_leftover_rows(seed_note_and_open);

		// nothing else is selected, so this is the add-and-remove path, not a rebuild
		picker().find(":checkbox[data-unit='title']").uncheck();
		cy.click_modal_primary_button("Update");

		web_form_fields().should((fields) => {
			expect(fields.map((d) => d.fieldname)).to.not.include("title");
		});
	});

	it("Keeps a field left over from the previous DocType at the end of a rebuild", () => {
		open_picker_on_leftover_rows(seed_note_and_open);

		// a form that already has rows defaults to Fields Only
		set_update_type("Fields with Layout");
		// everything selected rebuilds in doctype order, and `title` is in no order at all
		picker().find('[data-action="select_all"]').click();
		cy.click_modal_primary_button("Update");

		web_form_fields().should((fields) => {
			expect(fields.at(-1).fieldname, "the left over row is last").to.eq("title");
		});
	});
});
