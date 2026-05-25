const DOCTYPE = "DocType";
const LIST_URL = "/desk/List/DocType/List";

// Columns with a fixed starting width so drag tests have a predictable baseline
// and never start at the natural flexbox width (which can vary by viewport).
const BASE_FIELDS = JSON.stringify([
	{ fieldname: "name", label: "Name" },
	{ fieldname: "module", label: "Module", width: 150 },
]);

// Helper — open List View Settings modal for the current list
function openListSettings() {
	cy.get(".menu-btn-group button").click({ force: true });
	cy.get(".dropdown-menu li").filter(":visible").contains("List Settings").click();
	cy.get(".modal-dialog").should("contain", `${DOCTYPE} List View Settings`);
}

// Helper — reset List View Settings to a clean, known state before each test.
function resetListViewSettings() {
	cy.call("frappe.desk.doctype.list_view_settings.list_view_settings.save_listview_settings", {
		doctype: DOCTYPE,
		listview_settings: { fields: BASE_FIELDS },
		removed_listview_fields: [],
	});
}

// Helper — get the rendered pixel width of a list-row-col by fieldname
function getColumnWidth(fieldname) {
	return cy
		.get(`.list-row-head .list-row-col[data-fieldname="${fieldname}"]`)
		.invoke("outerWidth");
}

// Helper — simulate drag-to-resize using jQuery $.Event so that both the
// delegated mousedown handler on $result and the document-level
// mousemove/mouseup handlers receive events with the right pageX values.
function dragResizeColumn(fieldname, deltaX) {
	cy.window().then((win) => {
		const $ = win.$;
		const handle = win.document.querySelector(
			`.list-row-head .list-row-col[data-fieldname="${fieldname}"] .list-col-resize-handle`
		);
		if (!handle) throw new Error(`Resize handle for "${fieldname}" not found`);

		const rect = handle.getBoundingClientRect();
		const startX = rect.left + rect.width / 2;

		// Trigger mousedown on the handle so jQuery's delegated handler on $result fires.
		$(handle).trigger($.Event("mousedown", { pageX: startX, which: 1, button: 0 }));
		// Trigger mousemove and mouseup on document where the drag listeners are registered.
		$(win.document).trigger($.Event("mousemove", { pageX: startX + deltaX }));
		$(win.document).trigger($.Event("mouseup", { pageX: startX + deltaX }));
	});
}

context("List View — Column Widths", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	beforeEach(() => {
		resetListViewSettings();
		cy.visit(LIST_URL);
		cy.wait(500);
		cy.clear_filters();
	});

	// ─── 1. Width set via List View Settings dialog is applied ───────────────────

	it("saves and applies column width set in List View Settings dialog", () => {
		openListSettings();

		// Scope to the modal to avoid ambiguous matches outside the dialog
		cy.get(".modal-dialog")
			.find('[data-fieldname="module"] input.form-control')
			.clear()
			.type("180");

		cy.findByRole("button", { name: "Save" }).click();

		// Wait for the dialog to close (it hides in the save callback)
		cy.get(".modal-dialog").should("not.be.visible");

		// Reload so fresh render applies the persisted width via setup_columns()
		cy.reload();
		cy.wait(500);

		getColumnWidth("module").should("be.closeTo", 180, 15);
	});

	// ─── 2. Width persists after page reload ─────────────────────────────────────

	it("persists column width across page reloads", () => {
		cy.call(
			"frappe.desk.doctype.list_view_settings.list_view_settings.save_listview_settings",
			{
				doctype: DOCTYPE,
				listview_settings: {
					fields: JSON.stringify([
						{ fieldname: "name", label: "Name" },
						{ fieldname: "module", label: "Module", width: 220 },
					]),
				},
				removed_listview_fields: [],
			}
		);

		cy.reload();
		cy.wait(500);

		getColumnWidth("module").should("be.closeTo", 220, 15);
	});

	// ─── 3. Drag-to-resize changes the column width ──────────────────────────────

	it("drag-to-resize handle changes column width", () => {
		// BASE_FIELDS seeds module at 150 px, so 150+80=230 — well inside the 400 px cap.
		getColumnWidth("module").then((initialWidth) => {
			dragResizeColumn("module", 80);
			cy.wait(300);
			getColumnWidth("module").should("be.greaterThan", initialWidth + 40);
		});
	});

	// ─── 4. Drag-to-resize width is persisted after reload ───────────────────────

	it("drag-to-resize width is persisted in List View Settings", () => {
		// BASE_FIELDS seeds module at 150 px, so 150+60=210 — well inside the 400 px cap.
		getColumnWidth("module").then((initialWidth) => {
			dragResizeColumn("module", 60);
			cy.wait(600);

			cy.reload();
			cy.wait(500);

			getColumnWidth("module").should("be.greaterThan", initialWidth + 30);
		});
	});

	// ─── 5. Min-width constraint (50 px) is enforced ─────────────────────────────

	it("enforces minimum column width of 50 px when dragging", () => {
		dragResizeColumn("module", -2000);
		cy.wait(300);
		getColumnWidth("module").should("be.gte", 50);
	});

	// ─── 6. Max-width constraint (400 px) is enforced ────────────────────────────

	it("enforces maximum column width of 400 px when dragging", () => {
		dragResizeColumn("module", 2000);
		cy.wait(300);
		getColumnWidth("module").should("be.lte", 400);
	});

	// ─── 7. Resize handles are present in the header ─────────────────────────────

	it("shows resize handles in the list header", () => {
		cy.get(".list-row-head .list-col-resize-handle").should("have.length.greaterThan", 0);
	});

	// ─── 8. List View Settings dialog shows Width (px) header and hint ───────────

	it("shows Width (px) column header and drag hint in List View Settings", () => {
		openListSettings();

		cy.get(".modal-dialog").should("contain", "Width (px)");
		cy.get(".modal-dialog [title]")
			.filter((_, el) => el.title.toLowerCase().includes("drag"))
			.should("exist");

		cy.get(".modal-dialog .btn-modal-close").click();
	});
});
