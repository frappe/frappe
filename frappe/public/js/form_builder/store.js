import { create_layout } from "./utils";

let stores = {};

export function getStore(doctype) {
	if (stores[doctype]) {
		return stores[doctype];
	}

	let options = {
		data() {
			return {
				doctype,
				fields: null,
				docfields: null,
				selected_field: null,
				layout: null,
				dirty: false,
			};
		},
		watch: {
			layout: {
				deep: true,
				handler() {
					this.dirty = true;
				},
			},
			doctype: {
				deep: true,
				handler() {
					this.dirty = true;
				},
			},
		},
		methods: {
			fetch() {
				return new Promise((resolve) => {
					frappe.model.clear_doc("DocType", this.doctype);
					frappe.model.with_doctype(this.doctype, () => {
						this.fields = frappe.get_meta(this.doctype).fields;
						frappe.model.with_doctype("DocField", () => {
							this.docfields = frappe.get_meta("DocField").fields;
							this.layout = this.get_layout();
							this.$nextTick(() => (this.dirty = false));
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
	};
	stores[doctype] = new Vue(options);
	return stores[doctype];
}

export let storeMixin = {
	inject: ["$store"],
	computed: {
		doctype() {
			return this.$store.doctype;
		},
		layout() {
			return this.$store.layout;
		},
		fields() {
			return this.$store.fields;
		},
		docfields() {
			return this.$store.docfields;
		},
		selected_field() {
			return this.$store.selected_field;
		},
	},
};
