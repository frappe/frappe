// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("DocType Layout", {
	onload(frm) {
		frm.page.wrapper.addClass("doctype-layout-full-width");
		if (!document.getElementById("doctype-layout-fw-style")) {
			const style = document.createElement("style");
			style.id = "doctype-layout-fw-style";
			style.textContent = `
				.doctype-layout-full-width .layout-side-section { display: none !important; }
				.doctype-layout-full-width .layout-main-section-wrapper {
					width: 100% !important;
					max-width: 100% !important;
				}
				/* The form builder mounts on the tab pane, which lacks the section +
				   column padding that .form-builder-container's negative margins offset.
				   Restore it (15px section + 15px column) so the layout and right
				   sidebar get the same padding as in Customize Form. */
				.doctype-layout-full-width #doctype-layout-tab_break_form {
					padding-left: 30px;
					padding-right: 30px;
				}
			`;
			document.head.appendChild(style);
		}
	},

	tab_break_form(frm) {
		frm.events.render_builder(frm);
	},

	before_save(frm) {
		let builder = frappe.layout_builder;
		if (builder?.store) {
			let result = builder.store.update_fields();
			if (typeof result === "string") {
				frappe.throw(result);
			}
		}
	},

	after_save(frm) {
		if (frappe.layout_builder?.store) {
			frappe.layout_builder.store.fetch();
		}
	},

	refresh(frm) {
		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.set_read_only();
			frm.fields
				.filter((f) => f.has_input)
				.forEach((f) => frm.set_df_property(f.df.fieldname, "read_only", "1"));
			frm.disable_save();
		}
		frm.events.add_buttons(frm);
		frm.events.render_builder(frm);
	},

	async document_type(frm) {
		if (frm.doc.document_type) {
			frm.set_value("fields", []);
			await frm.events.sync_fields(frm, false);
			frm.events.render_builder(frm);
		}
	},

	add_buttons(frm) {
		if (!frm.is_new() && frm.doc.document_type) {
			const label = frm.doc.title || frm.doc.name;
			frm.add_custom_button(__("Go to {0} List", [label]), () => {
				frappe.route_options = {
					...frappe.utils.parse_layout_condition_to_filters(frm.doc.condition),
					_layout: frm.doc.name,
				};
				frappe.set_route("List", frm.doc.document_type);
			});
		}

		frm.add_custom_button(__("Sync Fields"), async () => {
			await frm.events.sync_fields(frm, true);
			if (frappe.layout_builder?.store) {
				frappe.layout_builder.store.fetch();
			} else {
				frm.events.render_builder(frm);
			}
		});
	},

	async sync_fields(frm, notify) {
		frappe.dom.freeze(__("Fetching fields…"));
		const response = await frm.call({ doc: frm.doc, method: "sync_fields" });
		frappe.dom.unfreeze();

		if (!response.message) {
			notify && frappe.show_alert({ message: __("No changes to sync"), indicator: "blue" });
			return;
		}

		frm.dirty();
		frm.refresh_field("fields");

		if (notify) {
			const { added, removed } = response.message;
			const rows = (fields) =>
				fields.map((f) => `<li>${(f.label || f.fieldname).bold()}</li>`).join("");
			let msg = "";
			if (added.length) msg += `${__("Added")}:<ul>${rows(added)}</ul>`;
			if (removed.length) msg += `${__("Removed")}:<ul>${rows(removed)}</ul>`;
			if (msg)
				frappe.msgprint({ message: msg, indicator: "green", title: __("Synced Fields") });
		}
	},

	render_builder(frm) {
		if (!frm.doc.document_type) return;

		const wrapper = $(frm.fields_dict["form_builder"].wrapper).closest(".tab-pane");
		const builder = frappe.layout_builder;

		if (builder?.store && builder.frm === frm) {
			// frm (and the mounted Vue app) is reused across records of this DocType.
			// Re-fetch only when the record or its target doctype changed, so plain
			// refreshes don't wipe in-progress edits in the builder.
			if (builder.docname === frm.doc.name && builder.doctype === frm.doc.document_type) {
				return;
			}
			builder.docname = frm.doc.name;
			builder.doctype = frm.doc.document_type;
			builder.update_store();
			builder.setup_page_actions();
			builder.store.fetch();
			return;
		}

		if (builder) {
			builder.$wrapper = wrapper;
			builder.frm = frm;
			builder.page = frm.page;
			builder.docname = frm.doc.name;
			builder.doctype = frm.doc.document_type;
			builder.is_layout = true;
			builder.init(true);
			builder.store.fetch();
			return;
		}

		// `refresh` can fire more than once before the bundle loads — guard so
		// only one FormBuilder instance is ever mounted.
		if (frm._layout_builder_loading) return;
		frm._layout_builder_loading = true;

		frappe.require("form_builder.bundle.js").then(() => {
			frappe.layout_builder = new frappe.ui.FormBuilder({
				wrapper: wrapper,
				frm: frm,
				doctype: frm.doc.document_type,
				customize: false,
				is_layout: true,
			});
			frappe.layout_builder.docname = frm.doc.name;
			frm._layout_builder_loading = false;

			// tab.refresh() is invoked by refresh_tabs() on every layout.refresh() and
			// frm.refresh_field() call. It hides the tab when all its sections appear
			// empty — which always happens here because the form_builder HTML control
			// has no visible input and base_control.refresh() permanently adds .hide-control.
			// Override the instance method so the tab stays visible whenever the layout
			// builder is active, regardless of what the section scan finds.
			const form_tab = frm.layout?.tabs?.find((t) => t.df.fieldname === "tab_break_form");
			if (form_tab) {
				const _orig_tab_refresh = form_tab.refresh.bind(form_tab);
				form_tab.refresh = function () {
					_orig_tab_refresh();
					if (frappe.layout_builder) this.toggle(true);
				};
				form_tab.toggle(true);
			}
		});
	},
});
