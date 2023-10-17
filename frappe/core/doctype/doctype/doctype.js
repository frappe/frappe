// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on("DocType", {
	before_save: function (frm) {
		let form_builder = frappe.form_builder;
		if (form_builder?.store) {
			let fields = form_builder.store.update_fields();

			// if fields is a string, it means there is an error
			if (typeof fields === "string") {
				frappe.throw(fields);
			}
		}
	},
	after_save: function (frm) {
		if (
			frappe.form_builder &&
			frappe.form_builder.doctype === frm.doc.name &&
			frappe.form_builder.store
		) {
			frappe.form_builder.store.fetch();
		}
	},
	refresh: function (frm) {
		frm.set_query("role", "permissions", function (doc) {
			if (doc.custom && frappe.session.user != "Administrator") {
				return {
					query: "frappe.core.doctype.role.role.role_query",
					filters: [["Role", "name", "!=", "All"]],
				};
			}
		});

		if (frappe.session.user !== "Administrator" || !frappe.boot.developer_mode) {
			if (frm.is_new()) {
				frm.set_value("custom", 1);
			}
			frm.toggle_enable("custom", 0);
			frm.toggle_enable("is_virtual", 0);
			frm.toggle_enable("beta", 0);
		}

		if (!frm.is_new() && !frm.doc.istable) {
			if (frm.doc.issingle) {
				frm.add_custom_button(__("Go to {0}", [__(frm.doc.name)]), () => {
					window.open(`/app/${frappe.router.slug(frm.doc.name)}`);
				});
			} else {
				frm.add_custom_button(__("Go to {0} List", [__(frm.doc.name)]), () => {
					window.open(`/app/${frappe.router.slug(frm.doc.name)}`);
				});
			}
		}

		const customize_form_link = "<a href='/app/customize-form'>Customize Form</a>";
		if (!frappe.boot.developer_mode && !frm.doc.custom) {
			// make the document read-only
			frm.set_read_only();
			frm.dashboard.clear_comment();
			frm.dashboard.add_comment(
				__("DocTypes can not be modified, please use {0} instead", [customize_form_link]),
				"blue",
				true
			);
		} else if (frappe.boot.developer_mode) {
			frm.dashboard.clear_comment();
			let msg = __(
				"This site is running in developer mode. Any change made here will be updated in code."
			);
			msg += "<br>";
			msg += __("If you just want to customize for your site, use {0} instead.", [
				customize_form_link,
			]);
			frm.dashboard.add_comment(msg, "yellow", true);
		}

		if (frm.is_new()) {
			frm.events.set_default_permission(frm);
			frm.set_value("default_view", "List");
		} else {
			frm.toggle_enable("engine", 0);
		}

		// set label for "In List View" for child tables
		frm.get_docfield("fields", "in_list_view").label = frm.doc.istable
			? __("In Grid View")
			: __("In List View");

		frm.cscript.autoname(frm);
		frm.cscript.set_naming_rule_description(frm);
		frm.trigger("setup_default_views");

		render_form_builder(frm);
		frm.linked_field = "link_field";
		frm.child_doctype = frm.docname;
		frm.trigger("set_link_field");
	},
	set_link_field(frm) {
		let doc = frappe.unscrub(frm.child_doctype);
		console.log("here", doc);
		let update_options = (options) => {
			frm.fields_dict["filters"].grid.update_docfield_property(
				frm.linked_field,
				"options",
				options
			);
		};

		get_fields_for_doctype(doc).then((fields) => {
			let as_select_option = (df) => ({
				label: df.label,
				value: df.fieldname,
			});
			update_options(
				frm.linked_field === "field"
					? fields
							.filter(
								(field) =>
									!["Column Break", "Section Break", "HTML"].includes(
										field.fieldtype
									)
							)
							.map(as_select_option)
					: fields.filter((field) => field.fieldtype === "Link").map(as_select_option)
			);
		});
	},

	istable: (frm) => {
		if (frm.doc.istable && frm.is_new()) {
			frm.set_value("default_view", null);
		} else if (!frm.doc.istable && !frm.is_new()) {
			frm.events.set_default_permission(frm);
		}
	},

	set_default_permission: (frm) => {
		if (!(frm.doc.permissions && frm.doc.permissions.length)) {
			frm.add_child("permissions", { role: "System Manager" });
		}
	},

	is_tree: (frm) => {
		frm.trigger("setup_default_views");
	},

	is_calendar_and_gantt: (frm) => {
		frm.trigger("setup_default_views");
	},

	setup_default_views: (frm) => {
		frappe.model.set_default_views_for_doctype(frm.doc.name, frm);
	},
});

frappe.ui.form.on("DocField", {
	form_render(frm, doctype, docname) {
		frm.trigger("setup_fetch_from_fields", doctype, docname);
	},

	fieldtype: function (frm) {
		frm.trigger("max_attachments");
	},

	fields_add: (frm) => {
		frm.trigger("setup_default_views");
	},
});

frappe.ui.form.on("DocType Filter", {
	link_field: function (frm, cdt, cdn) {
		frm.linked_field = "field";
		let link_field = locals[cdt][cdn].link_field;
		frm.child_doctype = frappe
			.get_meta(frm.docname)
			.fields.find((df) => df.fieldname === link_field)?.options;
		frm.trigger("set_link_field");
	},

	field: function (frm, cdt, cdn) {
		let current_doc = frappe.unscrub(locals[cdt][cdn].link_field);
		let current_doc_field_name = locals[cdt][cdn].field;
		let conditons = get_conditions_from_field(current_doc, current_doc_field_name);

		let as_select_option = (condition) => ({
			label: condition[1],
			value: condition[0],
		});

		frm.fields_dict["filters"].grid.update_docfield_property(
			"condition",
			"options",
			conditons.map(as_select_option)
		);
		let current_df = frappe
			.get_meta(current_doc)
			.fields.filter((f) => f.fieldname === current_doc_field_name)[0];
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

function render_form_builder_message(frm) {
	$(frm.fields_dict["try_form_builder_html"].wrapper).empty();
	if (!frm.is_new() && frm.fields_dict["try_form_builder_html"]) {
		let title = __("Use Form Builder to visually edit your form layout");
		let msg = __(
			"You can drag and drop fields to create your form layout, add tabs, sections and columns to organize your form and update field properties all from one screen."
		);

		let message = `
		<div class="flex form-message blue p-3">
			<div class="mr-3"><img style="border-radius: var(--border-radius-md)" width="360" src="/assets/frappe/images/form-builder.gif"></div>
			<div>
				<p style="font-size: var(--text-lg)">${title}</p>
				<p>${msg}</p>
				<div>
					<a class="btn btn-primary btn-sm" href="/app/form-builder/${frm.doc.name}">
						${__("Form Builder")} ${frappe.utils.icon("right", "xs")}
					</a>
				</div>
			</div>
		</div>
		`;

		$(frm.fields_dict["try_form_builder_html"].wrapper).html(message);
	}
}

function get_conditions_from_field(doctype, fieldname) {
	const conditions = [
		["=", __("Equals")],
		["!=", __("Not Equals")],
		["like", __("Like")],
		["not like", __("Not Like")],
		["in", __("In")],
		["not in", __("Not In")],
		["is", __("Is")],
		[">", ">"],
		["<", "<"],
		[">=", ">="],
		["<=", "<="],
		["Between", __("Between")],
		["Timespan", __("Timespan")],
	];
	const invalid_conditions_map = {
		Date: ["like", "not like"],
		Datetime: ["like", "not like", "in", "not in", "=", "!="],
		Data: ["Between", "Timespan"],
		Select: ["like", "not like", "Between", "Timespan"],
		Link: ["Between", "Timespan", ">", "<", ">=", "<="],
		Currency: ["Between", "Timespan"],
		Color: ["Between", "Timespan"],
		Check: conditions.map((c) => c[0]).filter((c) => c !== "="),
		Code: ["Between", "Timespan", ">", "<", ">=", "<=", "in", "not in"],
		"HTML Editor": ["Between", "Timespan", ">", "<", ">=", "<=", "in", "not in"],
		"Markdown Editor": ["Between", "Timespan", ">", "<", ">=", "<=", "in", "not in"],
		Password: ["Between", "Timespan", ">", "<", ">=", "<=", "in", "not in"],
		Rating: ["like", "not like", "Between", "in", "not in", "Timespan"],
		Float: ["like", "not like", "Between", "in", "not in", "Timespan"],
	};
	let current_df = frappe.get_meta(doctype).fields.filter((f) => f.fieldname === fieldname);
	let invalid_conditions = invalid_conditions_map[current_df[0].fieldtype] || [];
	return conditions.filter((c) => !invalid_conditions.includes(c[0]));
}

function render_form_builder(frm) {
	if (frappe.form_builder && frappe.form_builder.doctype === frm.doc.name) {
		frappe.form_builder.setup_page_actions();
		frappe.form_builder.store.fetch();
		return;
	}

	if (frappe.form_builder) {
		frappe.form_builder.wrapper = $(frm.fields_dict["form_builder"].wrapper);
		frappe.form_builder.frm = frm;
		frappe.form_builder.doctype = frm.doc.name;
		frappe.form_builder.customize = false;
		frappe.form_builder.init(true);
		frappe.form_builder.store.fetch();
	} else {
		frappe.require("form_builder.bundle.js").then(() => {
			frappe.form_builder = new frappe.ui.FormBuilder({
				wrapper: $(frm.fields_dict["form_builder"].wrapper),
				frm: frm,
				doctype: frm.doc.name,
				customize: false,
			});
		});
	}
}

extend_cscript(cur_frm.cscript, new frappe.model.DocTypeController({ frm: cur_frm }));
