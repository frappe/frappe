import { defineStore } from "pinia";
import { create_layout } from "./utils";
import { nextTick } from "vue";

export const useStore = defineStore("store", {
	state: () => ({
		doctype: "",
		doc: null,
		docfields: [],
		layout: {},
		active_tab: "",
		selected_field: null,
		dirty: false,
	}),
	getters: {
		selected: (state) => {
			return (name) => state.selected_field?.name == name;
		},
		get_df() {
			return (fieldtype, fieldname = "", label = "") => {
				let df = frappe.model.get_new_doc("DocField");
				df.name = frappe.utils.get_random(8);
				df.fieldtype = fieldtype;
				df.fieldname = fieldname;
				df.label = label;
				return df;
			};
		},
	},
	actions: {
		async fetch() {
			await frappe.model.clear_doc("DocType", this.doctype);
			await frappe.model.with_doctype(this.doctype);
			this.doc = frappe.get_doc("DocType", this.doctype);

			if (!this.docfields.length) {
				await frappe.model.with_doctype("DocField");
				this.docfields = frappe.get_meta("DocField").fields;
			}

			this.layout = this.get_layout();
			nextTick(() => (this.dirty = false));
		},
		async reset_changes() {
			await this.fetch();
			let first_tab = this.layout.tabs[0];
			this.active_tab = first_tab.df.name;
			this.selected_field = null;
		},
		save_changes() {
			if (!this.dirty) {
				frappe.show_alert({ message: __("No changes to save"), indicator: "orange" });
				return;
			}

			frappe.dom.freeze(__("Saving..."));

			let fields = [];
			let idx = 0;

			this.layout.tabs.forEach((tab) => {
				idx++;
				tab.df.idx = idx;
				fields.push(tab.df);

				tab.sections
					.filter((section) => !section.remove)
					.forEach((section, i) => {
						// do not consider first section if label is not set
						if ((i == 0 && section.df.label) || i > 0) {
							idx++;
							section.df.idx = idx;
							fields.push(section.df);
						}

						section.columns
							.filter((column) => !column.remove)
							.forEach((column, j) => {
								// do not consider first column
								if (j > 0) {
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

			// update fields table with latest changes
			this.doc.fields = fields;

			frappe
				.call("frappe.client.save", {
					doc: this.doc,
				})
				.then(() => {
					this.fetch();
					frappe.toast("Fields Table Updated");
				})
				.always(() => frappe.dom.unfreeze());
		},
		get_layout() {
			return create_layout(this.doc.fields, this.get_df);
		},
	},
});
