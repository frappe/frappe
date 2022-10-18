import { defineStore } from "pinia";
import { create_layout } from "./utils";
import { nextTick } from "vue";

export const useStore = defineStore("store", {
	state: () => ({
		doctype: "",
		fields: [],
		docfields: [],
		layout: {},
		dirty: false,
	}),
	actions: {
		fetch() {
			return new Promise((resolve) => {
				frappe.model.clear_doc("DocType", this.doctype);
				frappe.model.with_doctype(this.doctype, () => {
					this.fields = frappe.get_meta(this.doctype).fields;
					frappe.model.with_doctype("DocField", () => {
						this.docfields = frappe.get_meta("DocField").fields;
						this.layout = this.get_layout();
						nextTick(() => (this.dirty = false));
						resolve();
					});
				});
			});
		},
		reset_changes() {
			this.fetch();
		},
		get_layout() {
			return create_layout(this.fields);
		},
	},
});
