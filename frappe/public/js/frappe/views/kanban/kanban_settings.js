export default class KanbanSettings {
	constructor({ kanbanview, doctype, meta, settings }) {
		if (!doctype) {
			frappe.throw(__("DocType required"));
		}

		this.kanbanview = kanbanview;
		this.doctype = doctype;
		this.meta = meta;
		this.settings = settings;
		this.dialog = null;
		this.fields = this.settings && this.settings.fields;

		frappe.model.with_doctype("List View Settings", () => {
			this.make();
			this.get_fields();
			this.setup_fields();
			this.setup_remove_fields();
			this.add_new_fields();
			this.show_dialog();
		});
	}

	make() {
		this.dialog = new frappe.ui.Dialog({
			title: __("{0} Settings", [__(this.doctype)]),
			fields: [
				{
					fieldname: "show_labels",
					label: __("Show Labels"),
					fieldtype: "Check",
				},
				{
					fieldname: "fields_html",
					fieldtype: "HTML",
				},
				{
					fieldname: "fields",
					fieldtype: "Code",
					hidden: 1,
				},
			],
		});
		this.dialog.set_values(this.settings);
		this.dialog.set_primary_action(__("Save"), () => {
			frappe.show_alert({
				message: __("Saving"),
				indicator: "green",
			});

			frappe.call({
				method: "frappe.desk.doctype.kanban_board.kanban_board.save_settings",
				args: {
					board_name: this.settings.name,
					settings: this.dialog.get_values(),
				},
				callback: (r) => {
					this.kanbanview.board = r.message;
					this.kanbanview.render();
					this.dialog.hide();
				},
			});
		});
	}

	refresh() {
		this.setup_fields();
		this.add_new_fields();
		this.setup_remove_fields();
	}

	show_dialog() {
		if (!this.settings.fields) {
			this.update_fields();
		}

		this.dialog.show();
	}

	setup_fields() {
		const fields_html = this.dialog.get_field("fields_html");
		const wrapper = fields_html.$wrapper[0];
		let fields = "";

		for (let fieldname of this.fields) {
			let field = this.get_docfield(fieldname);

			fields += `
				<div class="control-input flex align-center form-control fields_order sortable"
					style="display: block; margin-bottom: 5px;"
					data-fieldname="${field.fieldname}"
					data-label="${field.label}"
					data-type="${field.type}">

					<div class="row">
						<div class="col-md-1">
							${frappe.utils.icon("drag", "xs", "", "", "sortable-handle")}
						</div>
						<div class="col-md-10" style="padding-left:0px;">
							${__(field.label, null, field.parent)}
						</div>
						<div class="col-md-1">
							<a class="text-muted remove-field" data-fieldname="${field.fieldname}">
								${frappe.utils.icon("delete", "xs")}
							</a>
						</div>
					</div>
				</div>`;
		}

		fields_html.html(`
			<div class="form-group">
				<div class="clearfix">
					<label class="control-label" style="padding-right: 0px;">${__("Fields")}</label>
				</div>
				<div class="control-input-wrapper">
				${fields}
				</div>
				<p class="help-box small text-muted">
					<a class="add-new-fields text-muted">
						${__("+ Add / Remove Fields")}
					</a>
				</p>
			</div>
		`);

		new Sortable(wrapper.getElementsByClassName("control-input-wrapper")[0], {
			handle: ".sortable-handle",
			draggable: ".sortable",
			onUpdate: (params) => {
				this.fields.splice(params.newIndex, 0, this.fields.splice(params.oldIndex, 1)[0]);
				this.dialog.set_value("fields", JSON.stringify(this.fields));
				this.refresh();
			},
		});
	}

	add_new_fields() {
		let add_new_fields =
			this.get_dialog_fields_wrapper().getElementsByClassName("add-new-fields")[0];
		add_new_fields.onclick = () => this.show_column_selector();
	}

	setup_remove_fields() {
		let remove_fields =
			this.get_dialog_fields_wrapper().getElementsByClassName("remove-field");

		for (let idx = 0; idx < remove_fields.length; idx++) {
			remove_fields.item(idx).onclick = () =>
				this.remove_fields(remove_fields.item(idx).getAttribute("data-fieldname"));
		}
	}

	get_dialog_fields_wrapper() {
		return this.dialog.get_field("fields_html").$wrapper[0];
	}

	remove_fields(fieldname) {
		this.fields = this.fields.filter((field) => field !== fieldname);
		this.dialog.set_value("fields", JSON.stringify(this.fields));
		this.refresh();
	}

	update_fields() {
		const wrapper = this.dialog.get_field("fields_html").$wrapper[0];
		let fields_order = wrapper.getElementsByClassName("fields_order");
		this.fields = [];

		for (let idx = 0; idx < fields_order.length; idx++) {
			this.fields.push(fields_order.item(idx).getAttribute("data-fieldname"));
		}

		this.dialog.set_value("fields", JSON.stringify(this.fields));
	}

	show_column_selector() {
		let dialog = new frappe.ui.Dialog({
			title: __("{0} Fields", [__(this.doctype)]),
			fields: [
				{
					label: __("Select Fields"),
					fieldtype: "MultiCheck",
					fieldname: "fields",
					options: this.get_multiselect_fields(),
					columns: 2,
				},
			],
		});
		dialog.set_primary_action(__("Save"), () => {
			this.fields = dialog.get_values().fields || [];
			this.dialog.set_value("fields", JSON.stringify(this.fields));
			this.refresh();
			dialog.hide();
		});
		dialog.show();
	}

	get_fields() {
		this.fields = this.settings.fields;
		this.fields.uniqBy((f) => f.fieldname);
	}

	get_docfield(field_name) {
		return (
			frappe.meta.get_docfield(this.doctype, field_name) ||
			frappe.model.get_std_field(field_name)
		);
	}

	get_multiselect_fields() {
		const ignore_fields = [
			"idx",
			"lft",
			"rgt",
			"old_parent",
			"_user_tags",
			"_liked_by",
			"_comments",
			"_assign",
			this.meta.title_field || "name",
		];

		const ignore_fieldtypes = [
			"Attach Image",
			"Text Editor",
			"HTML Editor",
			"Code",
			"Color",
			...frappe.model.no_value_type,
		];

		return frappe.model.std_fields
			.concat(this.kanbanview.get_fields_in_list_view())
			.filter(
				(field) =>
					!ignore_fields.includes(field.fieldname) &&
					!ignore_fieldtypes.includes(field.fieldtype)
			)
			.map((field) => {
				return {
					label: __(field.label, null, field.parent),
					value: field.fieldname,
					checked: this.fields.includes(field.fieldname),
				};
			});
	}
}
