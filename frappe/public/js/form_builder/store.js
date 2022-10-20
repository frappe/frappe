import { defineStore } from "pinia";
import { create_layout } from "./utils";
import { nextTick } from "vue";

export const useStore = defineStore("store", {
	state: () => ({
		doctype: "",
		fields: [],
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
			this.fields = frappe.get_meta(this.doctype).fields;

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
			this.selected_field = first_tab.df;
		},
		get_layout() {
			return create_layout(this.fields, this.get_df);
		},
	},
});
