/**
 * Board Settings dialog — lazy-loaded via `frappe.require("kanban_settings.bundle.js")`
 * so FieldGroup/grid weight stays out of the main kanban bundle.
 */
frappe.provide("frappe.views");

frappe.views.open_kanban_settings = function (page) {
	new KanbanBoardSettings(page).show();
};

class KanbanBoardSettings {
	constructor(page) {
		this.page = page;
		this.doctype = page.doctype;
		// Edit a deep clone so Cancel discards; the child tables are the arrays the
		// grids mutate in place, so `doc.<table>` always holds the current rows.
		this.doc = $.extend(true, {}, page.board_doc);
		["columns", "card_fields", "preview_fields", "group_by_fields"].forEach((t) => {
			// Sanitize child table rows to remove metadata that triggers permission checks.
			// Without this, controls see doctype/name and try to check permissions which fail
			// in dialog context (no frm). Keeping only the actual field values.
			this.doc[t] = (this.doc[t] || []).map((row, i) => this._sanitize_row(row, i + 1));
		});
	}

	/**
	 * Strip metadata properties from a child table row so grid controls treat it
	 * as a "new" row without triggering permission checks in base_control.get_status().
	 */
	_sanitize_row(row, idx) {
		const clean = { idx, __islocal: true };
		// Copy only the actual field values, skip framework metadata
		const skip = new Set([
			"doctype",
			"name",
			"parent",
			"parenttype",
			"parentfield",
			"owner",
			"creation",
			"modified",
			"modified_by",
			"docstatus",
			"idx",
			"__islocal",
			"__unsaved",
		]);
		for (const key in row) {
			if (!skip.has(key)) {
				clean[key] = row[key];
			}
		}
		return clean;
	}

	show() {
		frappe.model.with_doctype(this.doctype, () => {
			this.build_options();
			this.dialog = new frappe.ui.SettingsDialog({
				title: __("Board Settings"),
				default_tab: "config",
				tabs: this.make_tabs(),
			});
			this.dialog.show();
		});
	}

	/** Field option lists derived from the reference doctype meta (mirrors kanban_board.js). */
	build_options() {
		const meta = frappe.get_meta(this.doctype);
		const to_opt = (df) => ({
			value: df.fieldname,
			label: __(df.label) || df.fieldname,
			description: df.fieldname,
		});
		this.opts = {
			field_name: meta.fields
				.filter((d) => d.fieldname && d.fieldtype === "Select")
				.map((d) => d.fieldname),
			title: [{ value: "name", label: __("ID"), description: "name" }].concat(
				meta.fields
					.filter((d) => d.fieldname && d.fieldtype === "Data" && !d.hidden)
					.map(to_opt)
			),
			// Include the doctype's configured image_field even if hidden, since
			// image fields are often hidden in forms but used in sidebars/cards.
			image: meta.fields
				.filter(
					(d) =>
						d.fieldname &&
						d.fieldtype === "Attach Image" &&
						(!d.hidden || d.fieldname === meta.image_field)
				)
				.map(to_opt),
			card: meta.fields
				.filter(
					(d) =>
						d.fieldname &&
						frappe.model.is_value_type(d.fieldtype) &&
						!d.hidden &&
						d.fieldtype !== "Password"
				)
				.map(to_opt),
			group: meta.fields
				.filter(
					(d) =>
						d.fieldname &&
						(d.fieldtype === "Select" || d.fieldtype === "Link") &&
						!d.hidden
				)
				.map(to_opt),
		};
	}

	make_tabs() {
		return [
			{ group: __("General"), items: [this.config_item()] },
			{
				group: __("Layout"),
				items: [this.columns_item(), this.cards_item(), this.swimlanes_item()],
			},
		];
	}

	save_action() {
		return { label: __("Save"), variant: "solid", click: () => this.save() };
	}

	config_item() {
		return {
			id: "config",
			label: __("Config"),
			icon: "settings",
			title: __("Config"),
			description: __("How cards look in the new Kanban experience."),
			actions: [this.save_action()],
			fields: [
				{
					fieldname: "kanban_board_name",
					fieldtype: "Data",
					label: __("Board Name"),
					default: this.doc.kanban_board_name,
					read_only: 1,
				},
				{
					fieldname: "title_field",
					fieldtype: "Autocomplete",
					label: __("Title Field"),
					options: this.opts.title,
					default: this.doc.title_field,
					description: __(
						"Field shown as the card title. Only Name (ID) or Data fields."
					),
				},
				{
					fieldname: "image_field",
					fieldtype: "Autocomplete",
					label: __("Image Field"),
					options: this.opts.image,
					default: this.doc.image_field,
					description: __(
						"Attach Image field shown as a thumbnail before the card title."
					),
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "footer_date_field",
					fieldtype: "Select",
					label: __("Footer Date"),
					options: "Modified\nCreation",
					default: this.doc.footer_date_field || "Modified",
					description: __("Which timestamp to show in the card footer."),
				},
				{
					fieldname: "show_assigned_to",
					fieldtype: "Check",
					label: __("Show Assigned To"),
					default: this.doc.show_assigned_to,
				},
				{
					fieldname: "show_tags_on_card",
					fieldtype: "Check",
					label: __("Show Tags on Cards"),
					default: this.doc.show_tags_on_card,
				},
			],
		};
	}

	columns_item() {
		return {
			id: "columns",
			label: __("Columns"),
			icon: "kanban",
			title: __("Columns"),
			description: __("The field cards are grouped into columns by, and the column list."),
			actions: [this.save_action()],
			fields: [
				{
					fieldname: "field_name",
					fieldtype: "Select",
					label: __("Column Field"),
					options: this.opts.field_name,
					reqd: 1,
					default: this.doc.field_name,
					description: __("Select field whose options become the board columns."),
				},
				{
					fieldname: "columns",
					fieldtype: "Table",
					label: __("Columns"),
					data: this.doc.columns,
					cannot_add_rows: false,
					fields: [
						{
							fieldname: "column_name",
							fieldtype: "Data",
							label: __("Column Name"),
							in_list_view: 1,
							reqd: 1,
							columns: 5,
						},
						{
							fieldname: "status",
							fieldtype: "Select",
							label: __("Status"),
							options: "Active\nArchived",
							in_list_view: 1,
							columns: 2,
						},
						{
							fieldname: "indicator",
							fieldtype: "Select",
							label: __("Indicator"),
							options:
								"Blue\nCyan\nGray\nGreen\nLight Blue\nOrange\nPink\nPurple\nRed\nYellow",
							in_list_view: 1,
							columns: 3,
						},
					],
				},
			],
			render: (panel) => this.bind_field_name(panel),
		};
	}

	cards_item() {
		return {
			id: "cards",
			label: __("Cards"),
			icon: "list",
			title: __("Cards"),
			description: __("Fields shown on cards and in the hover preview."),
			actions: [this.save_action()],
			fields: [
				{
					fieldtype: "Section Break",
					label: __("Card Fields"),
				},
				{
					fieldname: "card_fields",
					fieldtype: "Table",
					data: this.doc.card_fields,
					cannot_add_rows: false,
					fields: this.field_grid_fields(true),
				},
				{
					fieldtype: "Section Break",
					label: __("Preview Fields"),
				},
				{
					fieldname: "preview_fields",
					fieldtype: "Table",
					data: this.doc.preview_fields,
					cannot_add_rows: false,
					fields: this.field_grid_fields(true),
				},
			],
			render: (panel) => {
				["card_fields", "preview_fields"].forEach((fn) =>
					this.set_grid_options(panel, fn, this.opts.card)
				);
			},
		};
	}

	swimlanes_item() {
		return {
			id: "swimlanes",
			label: __("Swimlanes"),
			icon: "layers",
			title: __("Swimlanes"),
			description: __("Fields the board can group cards into swimlanes by."),
			actions: [this.save_action()],
			fields: [
				{
					fieldname: "group_by_fields",
					fieldtype: "Table",
					label: __("Swimlanes (Group By)"),
					data: this.doc.group_by_fields,
					cannot_add_rows: false,
					fields: this.field_grid_fields(false),
				},
			],
			render: (panel) => this.set_grid_options(panel, "group_by_fields", this.opts.group),
		};
	}

	field_grid_fields(with_icon) {
		const f = [
			{
				fieldname: "fieldname",
				fieldtype: "Autocomplete",
				label: __("Field"),
				in_list_view: 1,
				reqd: 1,
				columns: with_icon ? 5 : 6,
			},
		];
		if (with_icon) {
			f.push({
				fieldname: "icon",
				fieldtype: "Icon",
				label: __("Icon"),
				in_list_view: 1,
				columns: 2,
			});
		}
		f.push({
			fieldname: "label",
			fieldtype: "Data",
			label: __("Label"),
			in_list_view: 1,
			columns: with_icon ? 3 : 4,
		});
		return f;
	}

	/** Fill a grid autocomplete column with the field option list (like the form's grids). */
	set_grid_options(panel, tablefield, options) {
		const grid = panel.get_field(tablefield) && panel.get_field(tablefield).grid;
		if (!grid || !grid.docfields) return;
		grid.update_docfield_property("fieldname", "options", options);
		grid.refresh();
	}

	/** Mirror the form: picking a new column field seeds the (empty) column list from
	 *  its Select options. Only when empty, so a configured column list isn't wiped. */
	bind_field_name(panel) {
		const field = panel.get_field("field_name");
		if (!field || !field.$input) return;
		field.$input.on("change", () => {
			if (this.doc.columns.length) return;
			const df = frappe.meta.get_field(this.doctype, panel.get_value("field_name"));
			if (!df) return;
			(df.options || "")
				.split("\n")
				.map((o) => o.trim())
				.filter(Boolean)
				.forEach((name) => this.doc.columns.push({ column_name: name, status: "Active" }));
			const grid = panel.get_field("columns") && panel.get_field("columns").grid;
			grid && grid.refresh();
		});
	}

	save() {
		// Collect values from all opened panels. The Table controls mutate their own
		// df.data arrays (via filter/push), so we must read from the grid directly.
		for (const panel of Object.values(this.dialog._panels || {})) {
			const values = panel.get_values();
			if (values === null) return; // a mandatory field is empty — control shows the error
			Object.assign(this.doc, values);
		}

		// Get the current data from each table grid (grids mutate df.data, not this.doc arrays)
		const tableFields = ["columns", "card_fields", "preview_fields", "group_by_fields"];
		for (const panel of Object.values(this.dialog._panels || {})) {
			for (const fieldname of tableFields) {
				const field = panel.get_field?.(fieldname);
				if (field?.grid?.df?.data) {
					this.doc[fieldname] = field.grid.df.data;
				}
			}
		}

		// Drop half-filled rows so the save isn't rejected for an empty mandatory cell.
		this.doc.columns = (this.doc.columns || []).filter((r) => (r.column_name || "").trim());
		["card_fields", "preview_fields", "group_by_fields"].forEach((t) => {
			this.doc[t] = (this.doc[t] || []).filter((r) => (r.fieldname || "").trim());
		});

		frappe.dom.freeze(__("Saving..."));
		frappe
			.call({ method: "frappe.client.save", args: { doc: this.doc } })
			.then((r) => {
				if (r.exc) return;
				this.page.board_doc = r.message;
				frappe.ui.toast({ message: __("Board settings saved"), type: "success" });
				this.dialog.hide();
				// Force a full reload so new columns / fields / toggles take effect.
				this.page.current_board = null;
				this.page.load_from_route();
			})
			.always(() => frappe.dom.unfreeze());
	}
}
