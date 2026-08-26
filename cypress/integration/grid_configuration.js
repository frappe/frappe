context("Grid Configuration", () => {
	// set by the footer test below; restored in afterEach so a failed
	// assertion never leaves the shared Website Settings singleton with the
	// test's rows instead of whatever was actually configured for the site.
	let saved_footer_items;

	beforeEach(() => {
		cy.login();
		cy.visit("/desk/website-settings");
	});

	afterEach(() => {
		if (!saved_footer_items) return;
		let footer_items_to_restore = saved_footer_items;
		saved_footer_items = undefined;

		cy.window()
			.its("cur_frm")
			.then((frm) => {
				frm.clear_table("footer_items");
				footer_items_to_restore.forEach((row) => frm.add_child("footer_items", row));
				frm.refresh_field("footer_items");
			});
		cy.save();
	});

	it("Set user wise grid settings", () => {
		cy.findByRole("tab", { name: "Navbar" }).click();
		cy.wait(100);
		cy.get('.frappe-control[data-fieldname="top_bar_items"]').as("table");
		cy.get("@table").find(".icon-sm").click();
		cy.wait(100);
		cy.get('.frappe-control[data-fieldname="fields_html"]').as("modal");
		cy.get("@modal").find(".add-new-fields").click();
		cy.wait(100);
		cy.get('[type="checkbox"][data-unit="right"]').check();
		cy.wait(100);
		cy.findByRole("button", { name: "Add" }).wait(100).click();
		cy.get('[data-fieldname="parent_label"]').invoke("attr", "value", "1");
		cy.get('.form-control.column-width[data-fieldname="parent_label"]').trigger("change");
		cy.findByRole("button", { name: "Update" }).click();
		cy.get('[title="Align Right"').should("be.visible");
	});

	it("Populates footer parent label options on page load (#20918)", () => {
		cy.findByRole("tab", { name: "Footer" }).click();
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				// snapshot only the editable fields, not full rows (name/idx/etc
				// belong to the rows being deleted and shouldn't be reused below)
				saved_footer_items = (frm.doc.footer_items || []).map((row) => ({
					label: row.label,
					url: row.url,
					parent_label: row.parent_label,
					right: row.right,
				}));

				frm.clear_table("footer_items");
				frm.add_child("footer_items", { label: "Products" });
				frm.add_child("footer_items", { label: "Phones" });
				frm.refresh_field("footer_items");
			});
		cy.save();

		// reload the page so onload_post_render actually runs; asserting in the
		// same session would go through the reactive (field-change) path instead
		// and mask the bug where options stayed empty on a fresh load
		cy.reload();
		cy.findByRole("tab", { name: "Footer" }).click();

		// .should() re-queries cur_frm and retries the assertion until it
		// passes or the command timeout elapses, instead of a fixed cy.wait()
		// racing onload_post_render on slower (CI) runs
		cy.window()
			.its("cur_frm")
			.should((frm) => {
				let parent_label_field = frm
					.get_field("footer_items")
					.grid.docfields.find((df) => df.fieldname === "parent_label");
				expect(parent_label_field.options).to.include("Products");
				expect(parent_label_field.options).to.include("Phones");
			});
	});
});
