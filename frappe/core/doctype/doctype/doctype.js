// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on("DocType", {
	setup: function (frm) {
		const savetrash = frm.savetrash.bind(frm);
		frm.savetrash = () =>
			frappe.listview_settings["DocType"].confirm_delete(
				[frm.doc.name],
				() =>
					frappe
						.call("frappe.client.delete", { doctype: "DocType", name: frm.doc.name })
						.then(() => {
							frappe.model.delete_from_locals("DocType", frm.doc.name);
							frappe.set_route("List", "DocType");
						}),
				savetrash
			);
	},

	onload: function (frm) {
		if (frm.is_new()) {
			frm.set_value("allow_auto_repeat", 0);
			if (!frm.doc?.fields) {
				frappe.listview_settings["DocType"].new_doctype_dialog();
			}
		}
		frm.call("check_pending_migration");
	},

	before_save: function (frm) {
		let form_builder = frappe.form_builder;
		if (form_builder?.store) {
			let fields = form_builder.store.update_fields();

			// if fields is a string, it means there is an error
			if (typeof fields === "string") {
				frappe.throw(fields);
			}
		}

		return frm.events.confirm_web_form_overwrite(frm);
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
				};
			}
		});

		if (frappe.session.user !== "Administrator" || !frappe.boot.developer_mode) {
			if (frm.is_new()) {
				frm.set_value("custom", 1);
			}
			frm.toggle_enable("custom", 0);
			frm.set_df_property(
				"custom",
				"description",
				__("Only Administrator can change this, in developer mode")
			);
			frm.toggle_enable("is_virtual", 0);
			frm.toggle_enable("beta", 0);
			frm.toggle_enable("deprecated", 0);
		}

		if (!frm.is_new() && !frm.doc.istable) {
			const button_text = frm.doc.issingle
				? __("Go to {0}", [__(frm.doc.name)])
				: __("Go to {0} List", [__(frm.doc.name)]);
			frm.add_custom_button(button_text, () => {
				window.open(`/desk/${frappe.router.slug(frm.doc.name)}`);
			});
		}

		const customize_form_link = `<a href="/desk/customize-form">${__("Customize Form")}</a>`;
		if (!frappe.boot.developer_mode && !frm.doc.custom) {
			// make the document read-only
			frm.set_read_only();
			frm.dashboard.clear_comment();
			frm.dashboard.add_comment(
				__("DocTypes cannot be modified, please use {0} instead", [customize_form_link]),
				"blue",
				true
			);
		} else if (frappe.boot.developer_mode) {
			frm.dashboard.clear_comment();
			let msg = __(
				"This site is running in developer mode. Any change made here will be updated in code."
			);
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

		if (!frm.is_dirty()) {
			frm.saved_fields = JSON.parse(JSON.stringify(frm.doc.fields || []));
		}

		frm.cscript.autoname(frm);
		frm.cscript.set_naming_rule_description(frm);
		frm.trigger("setup_default_views");

		render_form_builder(frm);
	},

	confirm_web_form_overwrite(frm) {
		const managed = frm.doc.__onload?.web_form_managed_fields;
		const changed = managed && get_fields_overwritten_by_web_form(frm, managed.fields);
		if (!changed?.length) return;

		return new Promise((resolve) => {
			let decided = false;
			const dialog = new frappe.ui.Dialog({
				title: __("Fields Managed by Web Form"),
				primary_action_label: __("Save Anyway"),
				primary_action: () => {
					decided = true;
					dialog.hide();
					resolve();
				},
				secondary_action_label: __("Discard"),
				secondary_action: () => {
					decided = true;
					frappe.validated = false;
					dialog.hide();
					frm.reload_doc().then(resolve);
				},
			});
			dialog.onhide = () => {
				if (decided) return;
				frappe.validated = false;
				resolve();
			};

			const web_form_link = `<a href="/desk/web-form/${encodeURIComponent(
				managed.web_form
			)}">${frappe.utils.escape_html(managed.web_form)}</a>`;
			dialog.$body.append(
				`<p>${__(
					"Web Form {0} manages these fields: {1}. Saving the Web Form overwrites your changes to them.",
					[web_form_link, changed.map((f) => frappe.utils.escape_html(f)).join(", ")]
				)}</p>`
			);
			dialog.show();
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

	on_tab_change: (frm) => {
		let current_tab = frm.get_active_tab().label;

		if (current_tab === "Form") {
			frm.footer.wrapper.hide();
			frm.form_wrapper.find(".form-message").hide();
			frm.form_wrapper.addClass("mb-1");
		} else {
			frm.footer.wrapper.show();
			frm.form_wrapper.find(".form-message").show();
			frm.form_wrapper.removeClass("mb-1");
		}
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

function get_fields_overwritten_by_web_form(frm, managed_fields) {
	const keys = ["label", "fieldtype", "options", "reqd", "default", "description"];
	const by_fieldname = (fields) =>
		Object.fromEntries((fields || []).map((df) => [df.fieldname, df]));
	const differs = (a, b) =>
		!a || !b ? a !== b : keys.some((key) => (a[key] || null) !== (b[key] || null));

	const current = by_fieldname(frm.doc.fields);
	const saved = by_fieldname(frm.saved_fields);
	return managed_fields
		.filter((managed) => {
			const df = current[managed.fieldname];
			return differs(df, managed) && differs(df, saved[managed.fieldname]);
		})
		.map((managed) => managed.label || managed.fieldname);
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

frappe.ui.form.set_controller("DocType", frappe.model.DocTypeController);
