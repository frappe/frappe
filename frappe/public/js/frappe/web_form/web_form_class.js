frappe.provide("frappe.ui");
frappe.provide("frappe.views");

window.web_form = null;
window.web_form_list = null;

frappe.ui.WebForm = class WebForm extends frappe.ui.FieldGroup {
	constructor(opts) {
		super();
		Object.assign(this, opts);
		window.web_form = this;
	}

	make(opts) {
		super.make();
		this.set_field_values();
		if (this.allow_delete) this.setup_delete_button();
		this.setup_primary_action();
	}

	set_field_values() {
		if (this.doc_name) this.set_values(this.doc);
		else return;
	}

	setup_primary_action() {
		const primary_action_button = document.createElement("button");
		primary_action_button.classList.add(
			"btn",
			"btn-primary",
			"primary-action",
			"btn-form-submit",
			"btn-sm",
			"ml-2"
		);
		primary_action_button.innerText = web_form.button_label || "Save";
		primary_action_button.onclick = () => this.save();
		document
			.querySelector(".web-form-actions")
			.appendChild(primary_action_button);
	}

	setup_delete_button() {
		const delete_button = document.createElement("button");
		delete_button.classList.add(
			"btn",
			"btn-danger",
			"button-delete",
			"btn-sm",
			"ml-2"
		);
		delete_button.innerText = "Delete";
		delete_button.onclick = () => this.delete();
		document.querySelector(".web-form-actions").appendChild(delete_button);
	}

	save() {
		// Handle data
		let data = this.get_values();
		if (this.doc) {
			Object.keys(data).forEach(field => (this.doc[field] = data[field]));
			data = this.doc;
		}
		if (!data || window.saving) return;
		data.doctype = this.doc_type;

		// Save
		window.saving = true;
		frappe.form_dirty = false;

		frappe.call({
			type: "POST",
			method: "frappe.website.doctype.web_form.web_form.accept",
			args: {
				data: data,
				web_form: this.name
			},
			callback: response => {
				// Check for any exception in response
				if (!response.exc) {
					// Success
					this.handle_success(response.message);
				}
			},
			always: function() {
				window.saving = false;
			}
		});
		return true;
	}

	delete() {
		frappe.call({
			type: "POST",
			method: "frappe.website.doctype.web_form.webform.delete",
			args: {
				web_form_name: this.name,
				docname: this.doc.name
			}
		})
	}

	handle_success(data) {
		const success_dialog = new frappe.ui.Dialog({
			title: __("Saved Successfully"),
			secondary_action: () => {
				if (this.login_required) {
					if (this.route_to_success_link) {
						window.location.pathname = this.success_url;
					} else {
						window.location.href =
							window.location.pathname + "?name=" + data.name;
					}
				}
			}
		});

		const success_message =
			this.success_message || __("Your information has been submitted");
		success_dialog.set_message(success_message);
		success_dialog.show();
	}
};

frappe.views.WebFormList = class WebFormList {
	constructor(opts) {
		Object.assign(this, opts);
		window.web_form_list = this;
		this.rows = []
		this.wrapper = document.getElementById("datatable")
		this.refresh_list();
		this.make_actions();
	}

	refresh_list() {
		if (this.table) {
			this.table.remove();
			delete this.table;
		}
		frappe.run_serially([
			() => this.get_list_view_fields(),
			() => this.get_data(),
			() => this.make_table()
		]);
	}

	get_list_view_fields() {
		return frappe
			.call({
				method:
					"frappe.website.doctype.web_form.web_form.get_in_list_view_fields",
				args: { doctype: this.doctype }
			})
			.then(response => this.fields_list = response.message);
	}

	get_data() {
		return frappe
			.call({
				method: "frappe.www.list.get_list_data",
				args: {
					doctype: this.doctype,
					fields: this.fields_list.map(df => df.fieldname),
					web_form_name: this.web_form_name
				}
			})
			.then(response => this.data = response.message);
	}

	make_table() {
		this.table = document.createElement("table");
		this.table.classList.add("table", "table-bordered", "table-hover");

		this.make_table_head();
		this.make_table_rows();

		this.wrapper.appendChild(this.table);
	}

	make_table_head() {
		// Create Heading
		let thead = this.table.createTHead();
		thead.style.backgroundColor = "#f7fafc";
		thead.style.color = "#8d99a6";
		let row = thead.insertRow();
		this.columns = this.fields_list.map(df => {
			return {
				label: df.label,
				fieldname: df.fieldname
			};
		});

		let th = document.createElement("th");

		let checkbox = document.createElement("input");
		checkbox.type = "checkbox";
		checkbox.onchange = event =>
			this.toggle_select_all(event.target.checked);

		th.appendChild(checkbox);
		row.appendChild(th);

		add_heading(row, "Sr.");
		this.columns.forEach(col => {
			let th = document.createElement("th");
			let text = document.createTextNode(col.label);
			th.appendChild(text);
			row.appendChild(th);
		});

		function add_heading(row, label) {
			let th = document.createElement("th");
			th.innerText = label;
			row.appendChild(th);
		}
	}

	make_table_rows() {
		const tbody = this.table.childNodes[1] || this.table.createTBody();
		this.data.forEach((data_item, index) => {
			let row_element = tbody.insertRow();
			row_element.setAttribute("id", data_item.name);

			let row = new frappe.ui.WebFromListRow({
				row: row_element,
				doc: data_item,
				columns: this.columns,
				serial_number: index + 1,
				events: {
					onEdit: () => this.open_form(data_item.name),
					onSelect: () => this.toggle_delete()
				}
			});

			this.rows.push(row);
		});
	}

	make_actions() {
		const actions = document.querySelector(".list-view-actions");
		const footer = document.querySelector(".list-view-footer");

		addButton(actions, "delete-rows", "danger", true, "Delete", () =>
			this.delete_rows()
		);
		addButton(
			actions,
			"new",
			"primary",
			false,
			"New",
			() => (window.location.href = window.location.pathname + "?new=1")
		);
		addButton(footer, "more", "secondary", false, "More", () =>
			this.get_more_data()
		);

		function addButton(wrapper, id, type, hidden, name, action) {
			const button = document.createElement("button");
			button.classList.add("btn", "btn-primary", "btn-sm", "ml-2");
			if (type == "secondary")
				button.classList.add(
					"btn",
					"btn-secondary",
					"btn-sm",
					"ml-2",
					"text-white"
				);
			if (type == "danger")
				button.classList.add(
					"btn",
					"btn-danger",
					"button-delete",
					"btn-sm",
					"ml-2"
				);

			button.id = id;
			button.innerText = name;
			button.hidden = hidden;

			button.onclick = action;
			wrapper.appendChild(button);
		}
	}

	toggle_select_all(checked) {
		this.rows.forEach(row => row.toggle_select(checked));
	}

	open_form(name) {
		window.location.href = window.location.pathname + "?name=" + name;
	}

	get_selected() {
		return this.rows.filter(row => row.is_selected());
	}

	toggle_delete() {
		let btn = document.getElementById("delete-rows");
		btn.hidden = !this.get_selected().length;
	}

	delete_rows() {
		frappe
			.call({
				type: "POST",
				method:
					"frappe.website.doctype.web_form.web_form.delete_multiple",
				args: {
					web_form_name: this.web_form_name,
					docnames: this.get_selected().map(row => row.doc.name)
				}
			})
			.then(() => this.refresh_list());
	}
};

frappe.ui.WebFromListRow = class WebFromListRow {
	constructor({ row, doc, columns, serial_number, events, options }) {
		Object.assign(this, { row, doc, columns, serial_number, events });
		this.make_row();
	}

	make_row() {
		// Add Checkboxes
		let th = document.createElement("th");

		this.checkbox = document.createElement("input");
		this.checkbox.type = "checkbox";
		this.checkbox.onchange = event =>
			this.toggle_select(event.target.checked);

		th.appendChild(this.checkbox);
		this.row.appendChild(th);

		// Add Serial Number
		let serialNo = this.row.insertCell();
		serialNo.innerText = this.serial_number;

		this.columns.forEach(field => {
			let cell = this.row.insertCell();
			let text = document.createTextNode(this.doc[field.fieldname] || "");
			cell.appendChild(text);
		});

		// this.row.onclick = () => this.events.onEdit();
		this.row.style.cursor = "pointer";
	}

	toggle_select(checked) {
		this.checkbox.checked = checked;
		this.events.onSelect(checked);
	}

	is_selected() {
		return this.checkbox.checked;
	}
};