export default class ListSettings {
	constructor({ listview, doctype, meta, settings }) {
		if (!doctype) {
			frappe.throw(__('Doctype required'));
		}

		this.listview = listview;
		this.doctype = doctype;
		this.meta = meta;
		this.settings = settings;
		this.dialog = null;
		this.fields = this.settings && this.settings.fields ? JSON.parse(this.settings.fields) : [];
		this.subject_field = null;

		frappe.model.with_doctype("List View Settings", () => {
			this.make();
			this.get_listview_fields(meta);
			this.setup_fields();
			this.setup_remove_fields();
			this.add_new_fields();
			this.show_dialog();
		});
	}

	make() {
		let me = this;

		let list_view_settings = frappe.get_meta("List View Settings");

		me.dialog = new frappe.ui.Dialog({
			title: __("{0} Settings", [__(me.doctype)]),
			fields: list_view_settings.fields
		});
		me.dialog.set_values(me.settings);
		me.dialog.set_primary_action(__('Save'), () => {
			let values = me.dialog.get_values();

			frappe.show_alert({
				message: __("Saving"),
				indicator: "green"
			});

			frappe.call({
				method: "frappe.desk.doctype.list_view_settings.list_view_settings.save_listview_settings",
				args: {
					doctype: me.doctype,
					listview_settings: values,
					removed_listview_fields: me.removed_fields || []
				},
				callback: function (r) {
					me.listview.refresh_columns(r.message.meta, r.message.listview_settings);
					me.dialog.hide();
				}
			});
		});

		me.dialog.fields_dict["total_fields"].df.onchange = () => me.refresh();
	}

	refresh() {
		let me = this;

		me.setup_fields();
		me.add_new_fields();
		me.setup_remove_fields();
	}

	show_dialog() {
		let me = this;

		if (!this.settings.fields) {
			me.update_fields();
		}

		if (!me.dialog.get_value("total_fields")) {
			let field_count = me.fields.length;

			if (field_count < 4) {
				field_count = 4;
			} else if (field_count > 10) {
				field_count = 4;
			}

			me.dialog.set_value("total_fields", field_count);
		}

		me.dialog.show();
	}

	setup_fields() {
		function is_status_field(field) {
			return field.fieldname === "status_field";
		}

		let me = this;

		let fields_html = me.dialog.get_field("fields_html");
		let wrapper = fields_html.$wrapper[0];
		let fields = ``;
		let total_fields = me.dialog.get_values().total_fields || me.settings.total_fields;

		for (let idx in me.fields) {
			if (idx == parseInt(total_fields)) {
				break;
			}
			let is_sortable = (idx == 0) ? `` : `sortable`;
			let show_sortable_handle = (idx == 0) ? `hide` : ``;
			let can_remove = (idx == 0 || is_status_field(me.fields[idx])) ? `hide` : ``;

			fields += `
				<div class="control-input flex align-center form-control fields_order ${is_sortable}"
					style="display: block; margin-bottom: 5px;" data-fieldname="${me.fields[idx].fieldname}"
					data-label="${me.fields[idx].label}" data-type="${me.fields[idx].type}">

					<div class="row">
						<div class="col-md-1">
							<i class="fa fa-bars text-muted sortable-handle ${show_sortable_handle}" aria-hidden="true"></i>
						</div>
						<div class="col-md-10" style="padding-left:0px;">
							${me.fields[idx].label}
						</div>
						<div class="col-md-1 ${can_remove}">
							<a class="text-muted remove-field" data-fieldname="${me.fields[idx].fieldname}">
								<i class="fa fa-trash-o" aria-hidden="true"></i>
							</a>
						</div>
					</div>
				</div>`;
		}

		fields_html.html(`
			<div class="form-group">
				<div class="clearfix">
					<label class="control-label" style="padding-right: 0px;">Fields</label>
				</div>
				<div class="control-input-wrapper">
				${fields}
				</div>
				<p class="help-box small text-muted hidden-xs">
					<a class="add-new-fields text-muted">
						+ Add / Remove Fields
					</a>
				</p>
			</div>
		`);

		new Sortable(wrapper.getElementsByClassName("control-input-wrapper")[0], {
			handle: '.sortable-handle',
			draggable: '.sortable',
			onUpdate: () => {
				me.update_fields();
				me.refresh();
			}
		});
	}

	add_new_fields() {
		let me = this;

		let fields_html = me.dialog.get_field("fields_html");
		let add_new_fields = fields_html.$wrapper[0].getElementsByClassName("add-new-fields")[0];
		add_new_fields.onclick = () => me.column_selector();
	}

	setup_remove_fields() {
		let me = this;

		let fields_html = me.dialog.get_field("fields_html");
		let remove_fields = fields_html.$wrapper[0].getElementsByClassName("remove-field");

		for (let idx = 0; idx < remove_fields.length; idx++) {
			remove_fields.item(idx).onclick = () => me.remove_fields(remove_fields.item(idx).getAttribute("data-fieldname"));
		}
	}

	remove_fields(fieldname) {
		let me = this;
		let existing_fields = me.fields.map(f => f.fieldname);

		for (let idx in me.fields) {
			let field = me.fields[idx];

			if (field.fieldname == fieldname) {
				me.fields.splice(idx, 1);
				break;
			}
		}
		me.set_removed_fields(me.get_removed_listview_fields(me.fields.map(f => f.fieldname), existing_fields));
		me.refresh();
		me.update_fields();
	}

	update_fields() {
		let me = this;

		let fields_html = me.dialog.get_field("fields_html");
		let wrapper = fields_html.$wrapper[0];

		let fields_order = wrapper.getElementsByClassName("fields_order");
		me.fields = [];

		for (let idx = 0; idx < fields_order.length; idx++) {
			me.fields.push({
				fieldname: fields_order.item(idx).getAttribute("data-fieldname"),
				label: fields_order.item(idx).getAttribute("data-label")
			});
		}

		me.dialog.set_value("fields", JSON.stringify(me.fields));
		me.dialog.get_value("fields");
	}

	column_selector() {
		let me = this;

		let d = new frappe.ui.Dialog({
			title: __("{0} Fields", [__(me.doctype)]),
			fields: [
				{
					label: __("Reset Fields"),
					fieldtype: "Button",
					fieldname: "reset_fields",
					click: () => me.reset_listview_fields(d)
				},
				{
					label: __("Select Fields"),
					fieldtype: "MultiCheck",
					fieldname: "fields",
					options: me.get_doctype_fields(me.meta, me.fields.map(f => f.fieldname)),
					columns: 2
				}
			]
		});
		d.set_primary_action(__('Save'), () => {
			let values = d.get_values().fields;

			me.set_removed_fields(me.get_removed_listview_fields(values, me.fields.map(f => f.fieldname)));

			me.fields = [];
			me.set_subject_field(me.meta);
			me.set_status_field();

			for (let idx in values) {
				let value = values[idx];

				if (me.fields.length === parseInt(me.dialog.get_values().total_fields)) {
					break;
				} else if (value != me.subject_field.fieldname) {
					let field = frappe.meta.get_docfield(me.doctype, value);
					if (field) {
						me.fields.push({
							label: field.label,
							fieldname: field.fieldname
						});
					}
				}
			}

			me.refresh();
			me.dialog.set_value("fields", JSON.stringify(me.fields));
			d.hide();
		});
		d.show();
	}

	reset_listview_fields(dialog) {
		let me = this;

		frappe.xcall("frappe.desk.doctype.list_view_settings.list_view_settings.get_default_listview_fields", {
			doctype: me.doctype
		}).then((fields) => {
			let field = dialog.get_field("fields");
			field.df.options = me.get_doctype_fields(me.meta, fields);
			dialog.refresh();
		});

	}

	get_listview_fields(meta) {
		let me = this;

		if (!me.settings.fields) {
			me.set_list_view_fields(meta);
		} else {
			me.fields = JSON.parse(this.settings.fields);
		}

		me.fields.uniqBy(f => f.fieldname);
	}

	set_list_view_fields(meta) {
		let me = this;

		me.set_subject_field(meta);
		me.set_status_field();

		meta.fields.forEach(field => {
			if (field.in_list_view && !in_list(frappe.model.no_value_type, field.fieldtype) &&
				me.subject_field.fieldname != field.fieldname) {

				me.fields.push({
					label: field.label,
					fieldname: field.fieldname
				});
			}
		});
	}

	set_subject_field(meta) {
		let me = this;

		me.subject_field = {
			label: "Name",
			fieldname: "name"
		};

		if (meta.title_field) {
			let field = frappe.meta.get_docfield(me.doctype, meta.title_field.trim());

			me.subject_field = {
				label: field.label,
				fieldname: field.fieldname
			};
		}

		me.fields.push(me.subject_field);
	}

	set_status_field() {
		let me = this;

		if (frappe.has_indicator(me.doctype)) {
			me.fields.push({
				type: "Status",
				label: "Status",
				fieldname: "status_field"
			});
		}
	}

	get_doctype_fields(meta, fields) {
		let multiselect_fields = [];

		meta.fields.forEach(field => {
			if (!in_list(frappe.model.no_value_type, field.fieldtype)) {
				multiselect_fields.push({
					label: field.label,
					value: field.fieldname,
					checked: in_list(fields, field.fieldname)
				});
			}
		});

		return multiselect_fields;
	}

	get_removed_listview_fields(new_fields, existing_fields) {
		let me = this;
		let removed_fields = [];

		if (frappe.has_indicator(me.doctype)) {
			new_fields.push("status_field");
		}

		existing_fields.forEach(column => {
			if (!in_list(new_fields, column)) {
				removed_fields.push(column);
			}
		});

		return removed_fields;
	}

	set_removed_fields(fields) {
		let me = this;

		if (me.removed_fields) {
			me.removed_fields.concat(fields);
		} else {
			me.removed_fields = fields;
		}
	}
}
