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
		this.filters = this.settings && this.settings.filters ? JSON.parse(this.settings.filters) : [];
		this.subject_field = null;
		this.removed_fields = [];
		this.removed_filters = [];

		frappe.model.with_doctype("List View Settings", () => {
			this.make();
			this.set_listview_fields(meta);
			this.set_listview_filters(meta);
			this.refresh();
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
					removed_listview_attr: {
						"removed_listview_fields": me.removed_fields || [],
						"removed_listview_filters": me.removed_filters || [],
					}
				},
				callback: function (r) {
					me.listview.refresh_fields(r.message.meta, r.message.listview_settings);
					me.dialog.hide();
				}
			});
		});
	}

	refresh() {
		let me = this;

		me.setup_listview_fields();
		me.setup_listview_filters();
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

	setup_listview_fields() {
		let me = this;

		me.dialog.fields_dict["total_fields"].df.onchange = () => me.setup_listview_fields();

		let fields_html = me.dialog.get_field("fields_html");
		let wrapper = fields_html.$wrapper[0];
		let fields = ``;
		let total_fields = me.dialog.get_values().total_fields || me.settings.total_fields;

		let is_status_field = function (field) {
			return field.fieldname === "status_field";
		}

		for (let idx in me.fields) {
			if (idx == parseInt(total_fields)) {
				break;
			}

			let is_sortable = (idx == 0) ? `` : `fields-sortable`;
			let show_sortable_handle = (idx == 0) ? `hide` : ``;
			let can_remove = (idx == 0 || is_status_field(me.fields[idx])) ? `hide` : ``;

			fields += `
				<div class="control-input flex align-center form-control fields_order ${is_sortable}"
					style="display: block; margin-bottom: 5px;" data-fieldname="${me.fields[idx].fieldname}"
					data-label="${me.fields[idx].label}" data-type="${me.fields[idx].type}">

					<div class="row">
						<div class="col-md-1">
							<i class="fa fa-bars text-muted fields-sortable-handle ${show_sortable_handle}" aria-hidden="true"></i>
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
					<label class="control-label" style="padding-right: 0px;">Listview Fields</label>
				</div>
				<div class="fields-control-input-wrapper">
				${fields}
				</div>
				<p class="help-box small text-muted hidden-xs">
					<a class="add-new-fields text-muted">
						+ Add / Remove Fields
					</a>
				</p>
			</div>
		`);

		new Sortable(wrapper.getElementsByClassName("fields-control-input-wrapper")[0], {
			handle: '.fields-sortable-handle',
			draggable: '.fields-sortable',
			onUpdate: () => {
				me.update_fields();

				// Refreshes the fields
				me.setup_listview_fields();
			}
		});

		// Delete field
		let remove_fields = fields_html.$wrapper[0].getElementsByClassName("remove-field");
		for (let idx = 0; idx < remove_fields.length; idx++) {
			remove_fields.item(idx).onclick = () => me.remove_listview_fields(remove_fields.item(idx).getAttribute("data-fieldname"));
		}

		// Fields selector
		let reset_fields = "frappe.desk.doctype.list_view_settings.list_view_settings.get_default_listview_fields";
		let active_fields = {};
		active_fields[me.meta.name] = me.fields.map(f => f.fieldname)
		let add_new_fields = fields_html.$wrapper[0].getElementsByClassName("add-new-fields")[0];
		add_new_fields.onclick = () => {
			me.fields_selector("for_list_fields", false, reset_fields, active_fields);
		}
	}

	setup_listview_filters() {

		let me = this;

		let filters_html = me.dialog.get_field("filters_html");
		let wrapper = filters_html.$wrapper[0];
		let filters = ``;

		for (let idx in me.filters) {
			filters += `
				<div class="control-input flex align-center form-control filters_order filters-sortable"
					style="display: block; margin-bottom: 5px;" data-fieldname="${me.filters[idx].fieldname}"
					data-doctype="${me.filters[idx].doctype}">

					<div class="row">
						<div class="col-md-1">
							<i class="fa fa-bars text-muted filters-sortable-handle" aria-hidden="true"></i>
						</div>
						<div class="col-md-10" style="padding-left:0px;">
							${me.filters[idx].label}
						</div>
						<div class="col-md-1">
							<a class="text-muted remove-filter" data-fieldname="${me.filters[idx].fieldname}"
								data-doctype="${me.filters[idx].doctype}">

								<i class="fa fa-trash-o" aria-hidden="true"></i>
							</a>
						</div>
					</div>
				</div>`;
		}

		filters_html.html(`
			<div class="form-group">
				<div class="clearfix">
					<label class="control-label" style="padding-right: 0px;">Listview Filters</label>
				</div>
				<div class="filters-control-input-wrapper">
				${filters}
				</div>
				<p class="help-box small text-muted hidden-xs">
					<a class="add-new-fields text-muted">
						+ Add / Remove Filters
					</a>
				</p>
			</div>
		`);

		new Sortable(wrapper.getElementsByClassName("filters-control-input-wrapper")[0], {
			handle: '.filters-sortable-handle',
			draggable: '.filters-sortable',
			onUpdate: () => {
				me.update_filters();

				// Refreshes the filters
				me.setup_listview_filters();
			}
		});

		// Delete filter
		let remove_filters = filters_html.$wrapper[0].getElementsByClassName("remove-filter");
		for (let idx = 0; idx < remove_filters.length; idx++) {
			remove_filters.item(idx).onclick = () => me.remove_listview_filters(remove_filters.item(idx).getAttribute("data-doctype"),
				remove_filters.item(idx).getAttribute("data-fieldname"));
		}

		// Filters selector
		let reset_filters = "frappe.desk.doctype.list_view_settings.list_view_settings.get_default_listview_filters";
		let add_new_filters = filters_html.$wrapper[0].getElementsByClassName("add-new-fields")[0];
		add_new_filters.onclick = () => me.fields_selector("for_list_filters", true, reset_filters, me.get_active_filters_fields());
	}

	get_active_filters_fields() {
		let me = this;

		let active_fields = {};

		active_fields[me.meta.name] = [];
		me.filters.forEach(field => {
			if (field.doctype === me.meta.name) {
				active_fields[me.meta.name].push(field.fieldname);
			}
		});

		frappe.meta.get_table_fields(me.doctype).map(df => {
			active_fields[df.options] = [];
			me.filters.forEach(field => {
				if (field.doctype === df.options) {
					active_fields[df.options].push(field.fieldname);
				}
			});
		});

		return active_fields
	}

	remove_listview_fields(fieldname) {
		let me = this;
		let existing_fields = me.fields;

		me.fields = [];
		existing_fields.filter(field => {
			if (field.fieldname !== fieldname) {
				me.fields.push(field);
			} else {
				me.removed_fields.push(field);
			}
		});

		me.dialog.set_value("fields", JSON.stringify(me.fields));
		me.setup_listview_fields();
	}

	remove_listview_filters(doctype, fieldname) {
		let me = this;
		let existing_filters = me.filters;

		me.filters = []
		existing_filters.forEach(filter => {
			if (filter.doctype === doctype && filter.fieldname === fieldname) {
				me.removed_filters.push(filter);
			} else {
				me.filters.push(filter);
			}
		});

		me.dialog.set_value("filters", JSON.stringify(me.filters));
		me.setup_listview_filters();
	}

	update_fields() {
		let me = this;

		let existing_fields = me.fields;
		me.fields = [];

		let wrapper = me.dialog.get_field("fields_html").$wrapper[0];
		let fields_order = wrapper.getElementsByClassName("fields_order");

		for (let idx = 0; idx < fields_order.length; idx++) {
			me.fields.push(existing_fields.find(fld =>
				fld.fieldname === fields_order.item(idx).getAttribute("data-fieldname")));
		}

		me.dialog.set_value("fields", JSON.stringify(me.fields));
	}

	update_filters() {
		let me = this;

		let existing_filters = me.filters;
		me.filters = []

		let wrapper = me.dialog.get_field("filters_html").$wrapper[0];
		let filters_order = wrapper.getElementsByClassName("filters_order");

		for (let idx = 0; idx < filters_order.length; idx++) {
			me.filters.push(existing_filters.find(flt =>
				flt.doctype === filters_order.item(idx).getAttribute("data-doctype") &&
				flt.fieldname === filters_order.item(idx).getAttribute("data-fieldname")));
		}

		me.dialog.set_value("filters", JSON.stringify(me.filters));
	}

	fields_selector(selector, with_table_fields, reset_cmd, active_fields) {
		let me = this;

		let d = new frappe.ui.Dialog({
			title: __("Fields"),
			fields: [
				{
					label: __("Reset Fields"),
					fieldtype: "Button",
					fieldname: "reset_fields",
					click: () => me.reset_options(d, reset_cmd)
				},
				...me.get_fields(me.meta, with_table_fields, active_fields)
			]
		});
		d.set_primary_action(__('Save'), () => {

			if (selector === "for_list_fields") {
				me.set_new_listview_fields(d.get_values());
			} else if (selector === "for_list_filters") {
				me.set_new_listview_filters(d.get_values());
			}

			d.hide();
		});

		d.show();
	}

	set_new_listview_fields(values) {
		let me = this;

		values = values[me.doctype];
		let existing_fields = me.fields;
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

		me.removed_fields.concat(me.get_removed(me.fields, existing_fields));

		me.setup_listview_fields();
		me.dialog.set_value("fields", JSON.stringify(me.fields));
	}

	set_new_listview_filters(values) {
		let me = this;

		let existing_filters = me.filters;
		me.filters = [];

		Object.keys(values).forEach(doctype => {
			frappe.model.with_doctype(doctype, () => {
				values[doctype].forEach(field => {
					let meta = frappe.get_meta(doctype);
					let df = frappe.meta.get_docfield(doctype, field);
					let label = meta.istable ? __("{0} ({1})", [df.label, doctype]) : __(df.label);
					let options = df.options;
					let condition = '=';
					let fieldtype = df.fieldtype;

					if (['Text', 'Small Text', 'Text Editor', 'HTML Editor', 'Data', 'Code', 'Read Only'].includes(fieldtype)) {
						fieldtype = 'Data';
						condition = 'like';
					}

					if (df.fieldtype == "Select" && df.options) {
						options = df.options.split("\n");
						if (options.length > 0 && options[0] != "") {
							options.unshift("");
							options = options.join("\n");
						}
					}

					let default_value = (fieldtype === 'Link') ? frappe.defaults.get_user_default(options) : null;
					if (['__default', '__global'].includes(default_value)) {
						default_value = null;
					}

					me.filters.push({
						doctype: doctype,
						fieldtype: fieldtype,
						label: label,
						options: options,
						fieldname: df.fieldname,
						condition: condition,
						default: default_value,
						ignore_link_validation: fieldtype === 'Dynamic Link',
						is_filter: 1
					})
				});
			});
		});

		me.removed_filters.concat(me.get_removed(me.filters, existing_filters));

		me.setup_listview_filters();
		me.dialog.set_value("filters", JSON.stringify(me.filters));
	}

	get_fields(meta, with_table_fields, active_fields) {
		let me = this;

		let fields = [
			{
				label: __(meta.name),
				fieldtype: 'MultiCheck',
				fieldname: meta.name,
				columns: 2,
				options: me.get_doctype_fields(meta, active_fields[meta.name])
			}
		];

		if (with_table_fields) {
			frappe.meta.get_table_fields(me.doctype).map(df => {
				let table_doctype = df.options;

				frappe.model.with_doctype(table_doctype, () => {
					let meta = frappe.get_meta(table_doctype);

					fields.push({
						label: __(meta.name),
						fieldtype: 'MultiCheck',
						fieldname: meta.name,
						columns: 2,
						options: me.get_doctype_fields(meta, active_fields[meta.name])
					});
				});
			});
		}

		return fields;
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

	reset_options(dialog, reset_cmd) {
		let me = this;

		frappe.xcall(reset_cmd, { doctype: me.doctype }).then((fields) => {
			Object.keys(fields).forEach(dt => {
				frappe.model.with_doctype(dt, () => {
					let meta = frappe.get_meta(dt);
					let field = dialog.get_field(dt);

					field.df.options = me.get_doctype_fields(meta, fields[dt]);
				});
			});
			dialog.refresh();
		});

	}

	set_listview_fields(meta) {
		let me = this;

		if (me.settings.fields) {
			return;
		}

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

	set_listview_filters(meta) {
		let me = this;

		if (me.settings.filters) {
			return;
		}

		let filters = {}
		filters[me.doctype] = []

		meta.fields.forEach(field => {
			if (field.in_standard_filter && !in_list(frappe.model.no_value_type, field.fieldtype)) {
				filters[me.doctype].push(field.fieldname);
			}
		});

		me.set_new_listview_filters(filters);
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

	get_removed(new_list, existing_list) {
		let me = this;
		let _new_list = {};
		let removed = [];

		let push_to_new_list = function (doctype, fieldname) {
			if (_new_list.hasOwnProperty(doctype)) {
				_new_list[doctype].push(fieldname);
			} else {
				_new_list[doctype] = [fieldname];
			}
		};

		let add_to_removed = function (list, el) {
			if (!list || !in_list(list, el.fieldname)) {
				removed.push(el);
			}
		};

		new_list.forEach(el => {
			push_to_new_list(el.hasOwnProperty("doctype") ? el.doctype : me.doctype, el.fieldname);
		})

		existing_list.forEach(el => {
			add_to_removed(el.hasOwnProperty("doctype") ? _new_list[el.doctype] : _new_list[me.doctype], el);
		});

		console.log(removed)
		return removed;
	}
}