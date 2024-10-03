frappe.ui.form.on("Web Form", {
	setup: function () {
		frappe.meta.docfield_map["Web Form Field"].fieldtype.formatter = (value) => {
			const prefix = {
				"Page Break": "--red-600",
				"Section Break": "--blue-600",
				"Column Break": "--yellow-600",
			};
			if (prefix[value]) {
				value = `<span class="bold" style="color: var(${prefix[value]})">${value}</span>`;
			}
			return value;
		};

		frappe.meta.docfield_map["Web Form Field"].fieldname.formatter = (value) => {
			if (!value) return;
			return frappe.unscrub(value);
		};

		frappe.meta.docfield_map["Web Form List Column"].fieldname.formatter = (value) => {
			if (!value) return;
			return frappe.unscrub(value);
		};
	},

	refresh: function (frm) {
		// get iframe url for web form
		frm.sidebar
			.add_user_action(__("Copy embed code"))
			.attr("href", "#")
			.on("click", () => {
				const url = frappe.urllib.get_full_url(frm.doc.route);
				const code = `<iframe src="${url}" style="border: none; width: 100%; height: inherit;"></iframe>`;
				frappe.utils.copy_to_clipboard(code, __("Embed code copied"));
			});

		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.disable_form();
			frappe.show_alert(
				__("Standard Web Forms can not be modified, duplicate the Web Form instead.")
			);
		}
		render_list_settings_message(frm);

		frm.trigger("set_fields");
		frm.trigger("add_get_fields_button");
		frm.trigger("add_publish_button");
		frm.trigger("render_condition_table");
	},

	login_required: function (frm) {
		render_list_settings_message(frm);
	},

	anonymous: function (frm) {
		if (frm.doc.anonymous) {
			frm.set_value("login_required", 0);
		}
	},

	validate: function (frm) {
		if (!frm.doc.login_required) {
			frm.set_value("allow_multiple", 0);
			frm.set_value("allow_edit", 0);
			frm.set_value("show_list", 0);
		}

		!frm.doc.allow_multiple && frm.set_value("allow_delete", 0);
		frm.doc.allow_multiple && frm.set_value("show_list", 1);

		if (!frm.doc.web_form_fields) {
			frm.scroll_to_field("web_form_fields");
			frappe.throw(__("At least one field is required in Web Form Fields Table"));
		}

		let page_break_count = frm.doc.web_form_fields.filter(
			(f) => f.fieldtype == "Page Break"
		).length;

		if (page_break_count >= 10) {
			frappe.throw(__("There can be only 9 Page Break fields in a Web Form"));
		}
	},

	add_publish_button(frm) {
		frm.add_custom_button(frm.doc.published ? __("Unpublish") : __("Publish"), () => {
			frm.set_value("published", !frm.doc.published);
			frm.save();
		});
	},

	add_get_fields_button(frm) {
		frm.add_custom_button(__("Get Fields"), () => {
			let webform_fieldtypes = frappe.meta
				.get_field("Web Form Field", "fieldtype")
				.options.split("\n");

			let added_fields = (frm.doc.web_form_fields || []).map((d) => d.fieldname);

			get_fields_for_doctype(frm.doc.doc_type).then((fields) => {
				for (let df of fields) {
					let fieldtype = df.fieldtype;
					if (fieldtype == "Tab Break") {
						fieldtype = "Page Break";
					}
					if (
						webform_fieldtypes.includes(fieldtype) &&
						!added_fields.includes(df.fieldname) &&
						!df.hidden
					) {
						frm.add_child("web_form_fields", {
							fieldname: df.fieldname,
							label: df.label,
							fieldtype: fieldtype,
							options: df.options,
							reqd: df.reqd,
							default: df.default,
							read_only: df.read_only,
							precision: df.precision,
							depends_on: df.depends_on,
							mandatory_depends_on: df.mandatory_depends_on,
							read_only_depends_on: df.read_only_depends_on,
						});
					}
				}
				frm.refresh_field("web_form_fields");
				frm.scroll_to_field("web_form_fields");
			});
		});
	},

	set_fields(frm) {
		let doc = frm.doc;

		let update_options = (options) => {
			[frm.fields_dict.web_form_fields.grid, frm.fields_dict.list_columns.grid].forEach(
				(obj) => {
					obj.update_docfield_property("fieldname", "options", options);
				}
			);
		};

		if (!doc.doc_type) {
			update_options([]);
			frm.set_df_property("amount_field", "options", []);
			return;
		}

		update_options([`Fetching fields from ${doc.doc_type}...`]);

		get_fields_for_doctype(doc.doc_type).then((fields) => {
			let as_select_option = (df) => ({
				label: df.label,
				value: df.fieldname,
			});
			update_options(fields.map(as_select_option));

			let currency_fields = fields
				.filter((df) => ["Currency", "Float"].includes(df.fieldtype))
				.map(as_select_option);
			if (!currency_fields.length) {
				currency_fields = [
					{
						label: `No currency fields in ${doc.doc_type}`,
						value: "",
						disabled: true,
					},
				];
			}
			frm.set_df_property("amount_field", "options", currency_fields);
		});
	},

	title: function (frm) {
		if (frm.doc.__islocal) {
			var page_name = frm.doc.title.toLowerCase().replace(/ /g, "-");
			frm.set_value("route", page_name);
		}
	},

	doc_type: function (frm) {
		frm.trigger("set_fields");
	},

	allow_multiple: function (frm) {
		frm.doc.allow_multiple && frm.set_value("show_list", 1);
	},

	before_save: function (frm) {
		let static_filters = JSON.parse(frm.doc.condition_json || "[]");
		frm.set_value("condition_json", JSON.stringify(static_filters));
		frm.trigger("render_condition_table");
	},

	render_condition_table: function (frm) {
		let wrapper = $(frm.get_field("condition_json").wrapper).empty();
		let table = $(`
			<style>
			.table-bordered th, .table-bordered td {
				border: none;
				border-right: 1px solid var(--border-color);
			}
			.table-bordered td {
				border-top: 1px solid var(--border-color);
			}
			.table thead th {
				border-bottom: none;
				font-weight: var(--weight-regular);
			}
			tr th:last-child, tr td:last-child{
				border-right: none;
			}
			thead {
				font-size: var(--text-sm);
				color: var(--gray-600);
				background-color: var(--subtle-fg);
			}
			thead th:first-child {
				border-top-left-radius: 9px;
			}
			thead th:last-child {
				border-top-right-radius: 9px;
			}
			</style>

			<table class="table table-bordered" style="cursor:pointer; margin:0px; border-radius: 10px; border-spacing: 0; border-collapse: separate;">
			<thead>
				<tr>
					<th>${__("Filter")}</th>
					<th style="width: 20%">${__("Condition")}</th>
					<th>${__("Value")}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);
		$(`<p class="text-muted small mt-2">${__("Click table to edit")}</p>`).appendTo(wrapper);

		let filters = JSON.parse(frm.doc.condition_json || "[]");
		let filters_set = false;

		let fields = [
			{
				fieldtype: "HTML",
				fieldname: "filter_area",
			},
		];

		if (filters?.length) {
			filters.forEach((filter) => {
				const filter_row = $(`<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`);

				table.find("tbody").append(filter_row);
			});
			filters_set = true;
		}

		if (!filters_set) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("Click to Set Filters")}</td></tr>`);
			table.find("tbody").append(filter_row);
		}

		table.on("click", () => {
			let dialog = new frappe.ui.Dialog({
				title: __("Set Filters"),
				fields: fields,
				primary_action: function () {
					let values = this.get_values();
					if (values) {
						this.hide();
						let filters = frm.filter_group.get_filters();
						frm.set_value("condition_json", JSON.stringify(filters));
						frm.trigger("render_condition_table");
					}
				},
				primary_action_label: "Set",
			});

			frm.filter_group = new frappe.ui.FilterGroup({
				parent: dialog.get_field("filter_area").$wrapper,
				doctype: frm.doc.doc_type,
				on_change: () => {},
			});
			filters && frm.filter_group.add_filters_to_filter_group(filters);

			dialog.show();

			dialog.set_values(filters);
		});
	},
});

frappe.ui.form.on("Web Form List Column", {
	fieldname: function (frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);
		let df = frappe.meta.get_docfield(frm.doc.doc_type, doc.fieldname);
		if (!df) return;
		doc.fieldtype = df.fieldtype;
		doc.label = df.label;
		frm.refresh_field("list_columns");
	},
});

frappe.ui.form.on("Web Form Field", {
	fieldtype: function (frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);

		if (doc.fieldtype == "Page Break") {
			let page_break_count = frm.doc.web_form_fields.filter(
				(f) => f.fieldtype == "Page Break"
			).length;
			page_break_count >= 10 &&
				frappe.throw(__("There can be only 9 Page Break fields in a Web Form"));
		}

		if (["Section Break", "Column Break", "Page Break"].includes(doc.fieldtype)) {
			doc.fieldname = "";
			doc.label = "";
			doc.options = "";
			frm.refresh_field("web_form_fields");
		}
	},
	fieldname: function (frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);
		let df = frappe.meta.get_docfield(frm.doc.doc_type, doc.fieldname);
		if (!df) return;

		doc.label = df.label;
		doc.fieldtype = df.fieldtype;
		doc.options = df.options;
		doc.reqd = df.reqd;
		doc.default = df.default;
		doc.read_only = df.read_only;
		doc.depends_on = df.depends_on;
		doc.mandatory_depends_on = df.mandatory_depends_on;
		doc.read_only_depends_on = df.read_only_depends_on;

		frm.refresh_field("web_form_fields");
	},
});

function get_fields_for_doctype(doctype) {
	return new Promise((resolve) => frappe.model.with_doctype(doctype, resolve)).then(() => {
		return frappe.meta.get_docfields(doctype).filter((df) => {
			return (
				(frappe.model.is_value_type(df.fieldtype) &&
					!["lft", "rgt"].includes(df.fieldname)) ||
				["Table", "Table Multiselect"].includes(df.fieldtype) ||
				frappe.model.layout_fields.includes(df.fieldtype)
			);
		});
	});
}

function render_list_settings_message(frm) {
	// render list setting message
	if (frm.fields_dict["list_setting_message"] && !frm.doc.login_required) {
		const go_to_login_required_field = `
			<code class="pointer" title="${__("Go to Login Required field")}">
				${__("login_required")}
			</code>
		`;
		let message = __(
			"Login is required to see web form list view. Enable {0} to see list settings",
			[go_to_login_required_field]
		);
		$(frm.fields_dict["list_setting_message"].wrapper)
			.html($(`<div class="form-message blue">${message}</div>`))
			.find("code")
			.click(() => frm.scroll_to_field("login_required"));
	} else {
		$(frm.fields_dict["list_setting_message"].wrapper).empty();
	}
}
