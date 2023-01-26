import { defineStore } from "pinia";
import { create_layout, scrub_field_names } from "./utils";
import { nextTick } from "vue";

export const useStore = defineStore("form-builder-store", {
	state: () => ({
		doctype: "",
		doc: null,
		docfields: [],
		custom_docfields: [],
		layout: {},
		active_tab: "",
		selected_field: null,
		dirty: false,
		read_only: false,
		is_customize_form: false,
		preview: false,
		drag: false,
	}),
	getters: {
		get_animation: () => {
			return "cubic-bezier(0.34, 1.56, 0.64, 1)";
		},
		selected: (state) => {
			return (name) => state.selected_field?.name == name;
		},
		get_docfields: (state) => {
			return state.is_customize_form ? state.custom_docfields : state.docfields;
		},
		get_df: (state) => {
			return (fieldtype, fieldname = "", label = "") => {
				let docfield = state.is_customize_form ? "Customize Form Field" : "DocField";
				let df = frappe.model.get_new_doc(docfield);
				df.name = frappe.utils.get_random(8);
				df.fieldtype = fieldtype;
				df.fieldname = fieldname;
				df.label = label;
				state.is_customize_form && (df.is_custom_field = 1);
				return df;
			};
		},
		has_standard_field: (state) => {
			return (field) => {
				if (!state.is_customize_form) return;
				if (!field.df.is_custom_field) return true;

				let children = {
					"Tab Break": "sections",
					"Section Break": "columns",
					"Column Break": "fields",
				}[field.df.fieldtype];

				if (!children) return false;

				return field[children].some((child) => {
					if (!child.df.is_custom_field) return true;
					return state.has_standard_field(child);
				});
			};
		},
		current_tab: (state) => {
			return state.layout.tabs.find((tab) => tab.df.name == state.active_tab);
		},
	},
	actions: {
		async fetch() {
			await frappe.model.clear_doc("DocType", this.doctype);
			await frappe.model.with_doctype(this.doctype);

			if (this.is_customize_form) {
				await frappe.model.with_doc("Customize Form");
				let doc = frappe.get_doc("Customize Form");
				doc.doc_type = this.doctype;
				let r = await frappe.call({ method: "fetch_to_customize", doc });
				this.doc = r.docs[0];
			} else {
				this.doc = await frappe.db.get_doc("DocType", this.doctype);
			}

			if (!this.get_docfields.length) {
				let docfield = this.is_customize_form ? "Customize Form Field" : "DocField";
				await frappe.model.with_doctype(docfield);
				let df = frappe.get_meta(docfield).fields;
				if (this.is_customize_form) {
					this.custom_docfields = df;
				} else {
					this.docfields = df;
				}
			}

			this.layout = this.get_layout();
			this.active_tab = this.layout.tabs[0].df.name;
			this.selected_field = null;

			nextTick(() => {
				this.dirty = false;
				this.read_only =
					!this.is_customize_form && !frappe.boot.developer_mode && !this.doc.custom;
				this.preview = false;
			});
		},
		reset_changes() {
			this.fetch();
		},
		validate_fields(fields, is_table) {
			fields = scrub_field_names(fields);

			let not_allowed_in_list_view = ["Attach Image", ...frappe.model.no_value_type];
			if (is_table) {
				not_allowed_in_list_view = not_allowed_in_list_view.filter((f) => f != "Button");
			}

			function get_field_data(df) {
				let fieldname = `<b>${df.label} (${df.fieldname})</b>`;
				if (!df.label) {
					fieldname = `<b>${df.fieldname}</b>`;
				}
				let fieldtype = `<b>${df.fieldtype}</b>`;
				return [fieldname, fieldtype];
			}

			fields.forEach((df) => {
				// check if fieldname already exist
				let duplicate = fields.filter((f) => f.fieldname == df.fieldname);
				if (duplicate.length > 1) {
					frappe.throw(__("Fieldname {0} appears multiple times", get_field_data(df)));
				}

				// Link & Table fields should always have options set
				if (in_list(["Link", ...frappe.model.table_fields], df.fieldtype) && !df.options) {
					frappe.throw(
						__("Options is required for field {0} of type {1}", get_field_data(df))
					);
				}

				// Do not allow if field is hidden & required but doesn't have default value
				if (df.hidden && df.reqd && !df.default) {
					frappe.throw(
						__(
							"{0} cannot be hidden and mandatory without any default value",
							get_field_data(df)
						)
					);
				}

				// In List View is not allowed for some fieldtypes
				if (df.in_list_view && in_list(not_allowed_in_list_view, df.fieldtype)) {
					frappe.throw(
						__(
							"'In List View' is not allowed for field {0} of type {1}",
							get_field_data(df)
						)
					);
				}

				// In Global Search is not allowed for no_value_type fields
				if (df.in_global_search && in_list(frappe.model.no_value_type, df.fieldtype)) {
					frappe.throw(
						__(
							"'In Global Search' is not allowed for field {0} of type {1}",
							get_field_data(df)
						)
					);
				}
			});
		},
		async save_changes() {
			if (!this.dirty) {
				frappe.show_alert({ message: __("No changes to save"), indicator: "orange" });
				return;
			}

			frappe.dom.freeze(__("Saving..."));

			try {
				if (this.is_customize_form) {
					let doc = frappe.get_doc("Customize Form");
					doc.doc_type = this.doctype;
					doc.fields = this.get_updated_fields();
					this.validate_fields(doc.fields, doc.istable);
					await frappe.call({ method: "save_customization", doc });
				} else {
					this.doc.fields = this.get_updated_fields();
					this.validate_fields(this.doc.fields, this.doc.istable);
					await frappe.call({
						method: "frappe.desk.form.save.savedocs",
						args: { doc: this.doc, action: "Save" },
					});
				}
				this.fetch();
			} catch (e) {
				console.error(e);
			} finally {
				frappe.dom.unfreeze();
			}
		},
		get_updated_fields() {
			let fields = [];
			let idx = 0;

			let layout_fields = JSON.parse(JSON.stringify(this.layout.tabs));

			layout_fields.forEach((tab, i) => {
				if (
					(i == 0 &&
						this.is_df_updated(tab.df, this.get_df("Tab Break", "", __("Details")))) ||
					i > 0
				) {
					idx++;
					tab.df.idx = idx;
					fields.push(tab.df);
				}

				tab.sections.forEach((section, j) => {
					// data before section is added
					let fields_copy = JSON.parse(JSON.stringify(fields));
					let old_idx = idx;
					section.has_fields = false;

					// do not consider first section if label is not set
					if (
						(j == 0 && this.is_df_updated(section.df, this.get_df("Section Break"))) ||
						j > 0
					) {
						idx++;
						section.df.idx = idx;
						fields.push(section.df);
					}

					section.columns.forEach((column, k) => {
						// do not consider first column if label is not set
						if (
							(k == 0 &&
								this.is_df_updated(column.df, this.get_df("Column Break"))) ||
							k > 0 ||
							column.fields.length == 0
						) {
							idx++;
							column.df.idx = idx;
							fields.push(column.df);
						}

						column.fields.forEach((field) => {
							idx++;
							field.df.idx = idx;
							fields.push(field.df);
							section.has_fields = true;
						});
					});

					// restore data back to data before section is added.
					if (!section.has_fields) {
						fields = fields_copy || [];
						idx = old_idx;
					}
				});
			});

			return fields;
		},
		is_df_updated(df, new_df) {
			delete df.name;
			delete new_df.name;
			return JSON.stringify(df) != JSON.stringify(new_df);
		},
		get_layout() {
			return create_layout(this.doc.fields);
		},
	},
});
