context("Grid Configuration", () => {
	// restored in afterEach(), even on failure, so the shared Website Settings singleton isn't left mutated
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

	it("Populates footer parent label options on page load", () => {
		cy.findByRole("tab", { name: "Footer" }).click();
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				saved_footer_items = (frm.doc.footer_items || []).map((row) => ({
					label: row.label,
					url: row.url,
					parent_label: row.parent_label,
					right: row.right,
					open_in_new_tab: row.open_in_new_tab,
				}));

				frm.clear_table("footer_items");
				frm.add_child("footer_items", { label: "Products" });
				frm.add_child("footer_items", { label: "Phones" });
				frm.refresh_field("footer_items");
			});
		cy.save();

		cy.reload();
		cy.findByRole("tab", { name: "Footer" }).click();

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
