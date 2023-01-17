context("Workspace 2.0", () => {
	before(() => {
		cy.visit("/login");
		cy.login();
	});

	it("Navigate to page from sidebar", () => {
		cy.visit("/app/build");
		cy.get(".codex-editor__redactor .ce-block");
		cy.get('.sidebar-item-container[item-name="Settings"]').first().click();
		cy.location("pathname").should("eq", "/app/settings");
	});

	it("Create Private Page", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.new_page",
		}).as("new_page");

		cy.get(".codex-editor__redactor .ce-block");
		cy.get('.custom-actions button[data-label="Create%20Workspace"]').click();
		cy.fill_field("title", "Test Private Page", "Data");
		cy.fill_field("icon", "edit", "Icon");
		cy.get_open_dialog().find(".modal-header").click();
		cy.get_open_dialog().find(".btn-primary").click();

		// check if sidebar item is added in pubic section
		cy.get('.sidebar-item-container[item-name="Test Private Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);

		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.wait(300);
		cy.get('.sidebar-item-container[item-name="Test Private Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);

		cy.wait("@new_page");
	});

	it("Create Child Page", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.new_page",
		}).as("new_page");

		cy.get(".codex-editor__redactor .ce-block");
		cy.get('.custom-actions button[data-label="Create%20Workspace"]').click();
		cy.fill_field("title", "Test Child Page", "Data");
		cy.fill_field("parent", "Test Private Page", "Select");
		cy.fill_field("icon", "edit", "Icon");
		cy.get_open_dialog().find(".modal-header").click();
		cy.get_open_dialog().find(".btn-primary").click();

		// check if sidebar item is added in pubic section
		cy.get('.sidebar-item-container[item-name="Test Child Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);

		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.wait(300);
		cy.get('.sidebar-item-container[item-name="Test Child Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);

		cy.wait("@new_page");
	});

	it("Duplicate Page", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.duplicate_page",
		}).as("page_duplicated");

		cy.get(".codex-editor__redactor .ce-block");
		cy.get(".standard-actions .btn-secondary[data-label=Edit]").click();

		cy.get('.sidebar-item-container[item-name="Test Private Page"]').as("sidebar-item");

		cy.get("@sidebar-item").find(".standard-sidebar-item").first().click();
		cy.get("@sidebar-item").find(".dropdown-btn").first().click();
		cy.get("@sidebar-item")
			.find(".dropdown-list .dropdown-item")
			.contains("Duplicate")
			.first()
			.click({ force: true });

		cy.get_open_dialog().fill_field("title", "Duplicate Page", "Data");
		cy.click_modal_primary_button("Duplicate");

		cy.wait("@page_duplicated");
	});

	it("Drag Sidebar Item", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.sort_pages",
		}).as("page_sorted");

		cy.get('.sidebar-item-container[item-name="Duplicate Page"]').as("sidebar-item");

		cy.get("@sidebar-item").find(".standard-sidebar-item").first().click();
		cy.get("@sidebar-item").find(".drag-handle").first().move({ deltaX: 0, deltaY: 100 });

		cy.get('.sidebar-item-container[item-name="Build"]').as("sidebar-item");

		cy.get("@sidebar-item").find(".standard-sidebar-item").first().click();
		cy.get("@sidebar-item").find(".drag-handle").first().move({ deltaX: 0, deltaY: 100 });

		cy.wait("@page_sorted");
	});

	it("Edit Page Detail", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.update_page",
		}).as("page_updated");

		cy.get('.sidebar-item-container[item-name="Test Private Page"]').as("sidebar-item");

		cy.get("@sidebar-item").find(".standard-sidebar-item").first().click();
		cy.get("@sidebar-item").find(".dropdown-btn").first().click();
		cy.get("@sidebar-item")
			.find(".dropdown-list .dropdown-item")
			.contains("Edit")
			.first()
			.click({ force: true });

		cy.get_open_dialog().fill_field("title", " 1", "Data");
		cy.get_open_dialog().find('input[data-fieldname="is_public"]').check();
		cy.click_modal_primary_button("Update");

		cy.get(
			'.standard-sidebar-section:first .sidebar-item-container[item-name="Test Private Page"]'
		).should("not.exist");
		cy.get(
			'.standard-sidebar-section:last .sidebar-item-container[item-name="Test Private Page 1"]'
		).should("exist");

		cy.wait("@page_updated");
	});

	it("Add New Block", () => {
		cy.get('.sidebar-item-container[item-name="Duplicate Page"]').as("sidebar-item");

		cy.get("@sidebar-item").find(".standard-sidebar-item").first().click();

		cy.get(".ce-block").click().type("{enter}");
		cy.get(".block-list-container .block-list-item").contains("Heading").click();
		cy.get(":focus").type("Header");
		cy.get(".ce-block:last").find(".ce-header").should("exist");

		cy.get(".ce-block:last").click().type("{enter}");
		cy.get(".block-list-container .block-list-item").contains("Text").click();
		cy.get(":focus").type("Paragraph text");
		cy.get(".ce-block:last").find(".ce-paragraph").should("exist");
	});

	it("Delete A Block", () => {
		cy.get(":focus").click();
		cy.get(".paragraph-control .setting-btn").click();
		cy.get(".paragraph-control .dropdown-item").contains("Delete").click();
		cy.get(".ce-block:last").find(".ce-paragraph").should("not.exist");
	});

	it("Shrink and Expand A Block", () => {
		cy.get(":focus").click();
		cy.get(".ce-block:last .setting-btn").click();
		cy.get(".ce-block:last .dropdown-item").contains("Shrink").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-11");
		cy.get(".ce-block:last .dropdown-item").contains("Shrink").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-10");
		cy.get(".ce-block:last .dropdown-item").contains("Shrink").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-9");
		cy.get(".ce-block:last .dropdown-item").contains("Expand").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-10");
		cy.get(".ce-block:last .dropdown-item").contains("Expand").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-11");
		cy.get(".ce-block:last .dropdown-item").contains("Expand").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-12");

		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
	});

	it("Hide/Unhide Workspaces", () => {
		// hide
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.hide_page",
		}).as("hide_page");

		cy.get(".codex-editor__redactor .ce-block");
		cy.get(".standard-actions .btn-secondary[data-label=Edit]").click();

		cy.get('.sidebar-item-container[item-name="Duplicate Page"]')
			.find(".sidebar-item-control .setting-btn")
			.click();
		cy.get('.sidebar-item-container[item-name="Duplicate Page"]')
			.find('.dropdown-item[title="Hide Workspace"]')
			.click({ force: true });
		cy.wait(300);
		cy.get('.standard-actions .btn-secondary[data-label="Discard"]').click();
		cy.get('.sidebar-item-container[item-name="Duplicate Page"]').should("not.be.visible");

		cy.wait("@hide_page");

		// unhide
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.unhide_page",
		}).as("unhide_page");

		cy.get(".codex-editor__redactor .ce-block");
		cy.get(".standard-actions .btn-secondary[data-label=Edit]").click();

		cy.get('.sidebar-item-container[item-name="Duplicate Page"]')
			.find('[title="Unhide Workspace"]')
			.click({ force: true });
		cy.wait(300);

		cy.get('.standard-actions .btn-secondary[data-label="Discard"]').click();
		cy.get('.sidebar-item-container[item-name="Duplicate Page"]').should("be.visible");

		cy.wait("@unhide_page");
	});

	it("Delete Duplicate Page", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.delete_page",
		}).as("page_deleted");

		cy.get(".codex-editor__redactor .ce-block");
		cy.get(".standard-actions .btn-secondary[data-label=Edit]").click();

		cy.get('.sidebar-item-container[item-name="Duplicate Page"]')
			.find(".sidebar-item-control .setting-btn")
			.click();
		cy.get('.sidebar-item-container[item-name="Duplicate Page"]')
			.find('.dropdown-item[title="Delete Workspace"]')
			.click({ force: true });
		cy.wait(300);
		cy.get(".modal-footer > .standard-actions > .btn-modal-primary:visible").first().click();
		cy.get('.sidebar-item-container[item-name="Duplicate Page"]').should("not.exist");

		cy.wait("@page_deleted");
	});
});
