// separate bundle so the dialog's grid controls stay out of kanban.bundle.js
frappe.provide("frappe.views");

frappe.views.open_kanban_settings = async function (page) {
	// the page's copy is stale once the board is saved elsewhere, e.g. by a column reorder
	page.board_doc = await frappe.db.get_doc("Kanban Board", page.board_doc.name);
	new KanbanBoardSettings(page).show();
};

class KanbanBoardSettings {
	constructor(page) {
		this.page = page;
		this.doctype = page.doctype;
		// deep clone so Cancel discards edits; grids mutate child rows in place
		this.doc = $.extend(true, {}, page.board_doc);
		["columns", "card_fields", "preview_fields", "group_by_fields"].forEach((t) => {
			// strip row metadata so grid controls skip permission checks
			this.doc[t] = (this.doc[t] || []).map((row, i) => this._sanitize_row(row, i + 1));
		});
	}

	_sanitize_row(row, idx) {
		const clean = { idx, __islocal: true };
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

	// mirrors the option lists in kanban_board.js
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
					.filter(
						(d) =>
							d.fieldname &&
							["Data", "Text", "Small Text", "Text Editor"].includes(d.fieldtype) &&
							!d.hidden
					)
					.map(to_opt)
			),
			// image fields are often hidden on the form, so hidden ones are allowed
			image: meta.fields
				.filter((d) => d.fieldname && d.fieldtype === "Attach Image")
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
			{
				group: __("Kanban Settings"),
				items: [
					this.config_item(),
					this.columns_item(),
					this.cards_item(),
					this.swimlanes_item(),
				],
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
				{ fieldtype: "Column Break" },
				{
					fieldname: "footer_date_field",
					fieldtype: "Select",
					label: __("Footer Date"),
					options: "Modified\nCreation",
					default: this.doc.footer_date_field || "Modified",
					description: __("Which timestamp to show in the card footer."),
				},
				{ fieldtype: "Section Break" },
				{
					fieldname: "title_field",
					fieldtype: "Autocomplete",
					label: __("Title Field"),
					options: this.opts.title,
					default: this.doc.title_field,
					description: __("ID or a text field."),
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "image_field",
					fieldtype: "Autocomplete",
					label: __("Image Field"),
					options: this.opts.image,
					default: this.doc.image_field,
					description: __("Attach Image field for card thumbnail."),
				},
				{ fieldtype: "Section Break" },
				{
					fieldname: "show_assigned_to",
					fieldtype: "Check",
					label: __("Show Assigned To"),
					default: this.doc.show_assigned_to,
				},
				{ fieldtype: "Column Break" },
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
				["card_fields", "preview_fields"].forEach((field) => {
					this.set_grid_options(panel, field, this.opts.card);
					this.bind_field_label_autofill(panel, field);
				});
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
			render: (panel) => {
				this.set_grid_options(panel, "group_by_fields", this.opts.group);
				this.bind_field_label_autofill(panel, "group_by_fields");
			},
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

	set_grid_options(panel, tablefield, options) {
		const grid = panel.get_field(tablefield) && panel.get_field(tablefield).grid;
		if (!grid || !grid.docfields) return;
		grid.update_docfield_property("fieldname", "options", options);
		grid.refresh();
	}

	bind_field_label_autofill(panel, tablefield) {
		const grid = panel.get_field(tablefield)?.grid;
		if (!grid) return;
		grid.wrapper.on("change", ".frappe-control[data-fieldname='fieldname'] input", (e) => {
			const fieldname = e.target.value;
			if (!fieldname) return;
			const df = frappe.meta.get_field(this.doctype, fieldname);
			if (!df) return;
			const $row = $(e.target).closest(".grid-row");
			const rowIdx = $row.data("idx");
			const row = grid.grid_rows.find((r) => r.doc.idx === rowIdx);
			if (row) {
				row.doc.label = df.label || fieldname;
				row.refresh_field("label");
			}
		});
	}

	// rebuild the columns from the new field's options, as the form does
	bind_field_name(panel) {
		const field = panel.get_field("field_name");
		if (!field || !field.$input) return;
		field.$input.on("change", () => {
			const df = frappe.meta.get_field(this.doctype, panel.get_value("field_name"));
			if (!df) return;
			const columns = (df.options || "")
				.split("\n")
				.map((o) => o.trim())
				.filter(Boolean)
				.map((name, i) => ({
					idx: i + 1,
					__islocal: true,
					column_name: name,
					status: "Active",
				}));
			// the grid holds this array, so replace its contents rather than the array
			this.doc.columns.splice(0, this.doc.columns.length, ...columns);
			const grid = panel.get_field("columns") && panel.get_field("columns").grid;
			grid && grid.refresh();
		});
	}

	save() {
		for (const panel of Object.values(this.dialog._panels || {})) {
			const values = panel.get_values();
			if (values === null) return; // a mandatory field is empty; the control shows the error
			Object.assign(this.doc, values);
		}

		const tableFields = ["columns", "card_fields", "preview_fields", "group_by_fields"];
		for (const panel of Object.values(this.dialog._panels || {})) {
			for (const fieldname of tableFields) {
				const field = panel.get_field?.(fieldname);
				if (field?.grid?.df?.data) {
					this.doc[fieldname] = field.grid.df.data;
				}
			}
		}

		// drop half-filled rows so the save isn't rejected for an empty mandatory cell
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
				// clear current_board to force a full reload
				this.page.current_board = null;
				this.page.load_from_route();
			})
			.always(() => frappe.dom.unfreeze());
	}
}
