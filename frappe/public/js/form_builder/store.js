import { defineStore } from "pinia";
import { create_layout } from "./utils";
import { nextTick } from "vue";

export const useStore = defineStore("store", {
	state: () => ({
		doctype: "",
		doc: null,
		docfields: [],
		custom_docfields: [],
		layout: {},
		active_tab: "",
		selected_field: null,
		dirty: false,
		is_customize_form: false,
	}),
	getters: {
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
		is_custom: (state) => {
			return (field) => {
				if (!state.is_customize_form) return;
				if (field.is_first) return 0;
				return field.df.is_custom_field;
			};
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
			nextTick(() => (this.dirty = false));
		},
		async reset_changes() {
			await this.fetch();
			let first_tab = this.layout.tabs[0];
			this.active_tab = first_tab.df.name;
			this.selected_field = null;
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
					await frappe.call({ method: "save_customization", doc });
				} else {
					this.doc.fields = this.get_updated_fields();
					await frappe.call("frappe.client.save", { doc: this.doc });
					frappe.toast("Fields Table Updated");
				}
				this.fetch();
			} finally {
				frappe.dom.unfreeze();
			}
		},
		get_updated_fields() {
			let fields = [];
			let idx = 0;

			this.layout.tabs.forEach((tab) => {
				if (!tab.is_first) {
					idx++;
					tab.df.idx = idx;
					fields.push(tab.df);
				}

				tab.sections
					.filter((section) => !section.remove)
					.forEach((section) => {
						// do not consider first section if label is not set
						if ((section.is_first && section.df.label) || !section.is_first) {
							idx++;
							section.df.idx = idx;
							fields.push(section.df);
						}

						section.columns
							.filter((column) => !column.remove)
							.forEach((column) => {
								// do not consider first column
								if (!column.is_first) {
									idx++;
									column.df.idx = idx;
									fields.push(column.df);
								}

								column.fields
									.filter((field) => !field.remove)
									.forEach((field) => {
										idx++;
										field.df.idx = idx;
										fields.push(field.df);
									});
							});
					});
			});

			return fields;
		},
		get_layout() {
			return create_layout(this.doc.fields, this.get_df);
		},
	},
});
