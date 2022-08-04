import { create_default_layout, pluck } from "./utils";

let stores = {};

export function getStore(print_format_name) {
	if (stores[print_format_name]) {
		return stores[print_format_name];
	}

	let options = {
		data() {
			return {
				print_format_name,
				letterhead_name: null,
				print_format: null,
				letterhead: null,
				doctype: null,
				meta: null,
				layout: null,
				dirty: false,
				edit_letterhead: false,
			};
		},
		watch: {
			layout: {
				deep: true,
				handler() {
					this.dirty = true;
				},
			},
			print_format: {
				deep: true,
				handler() {
					this.dirty = true;
				},
			},
		},
		methods: {
			fetch() {
				return new Promise((resolve) => {
					frappe.model.clear_doc("Print Format", this.print_format_name);
					frappe.model.with_doc("Print Format", this.print_format_name, () => {
						let print_format = frappe.get_doc("Print Format", this.print_format_name);
						frappe.model.with_doctype(print_format.doc_type, () => {
							this.meta = frappe.get_meta(print_format.doc_type);
							this.print_format = print_format;
							this.layout = this.get_layout();
							this.$nextTick(() => (this.dirty = false));
							this.edit_letterhead = false;
							resolve();
						});
					});
				});
			},
			update({ fieldname, value }) {
				this.$set(this.print_format, fieldname, value);
			},
			save_changes() {
				frappe.dom.freeze(__("Saving..."));

				this.layout.sections = this.layout.sections
					.filter((section) => !section.remove)
					.map((section) => {
						section.columns = section.columns.map((column) => {
							column.fields = column.fields
								.filter((df) => !df.remove)
								.map((df) => {
									if (df.table_columns) {
										df.table_columns = df.table_columns.map((tf) => {
											return pluck(tf, [
												"label",
												"fieldname",
												"fieldtype",
												"options",
												"width",
												"field_template",
											]);
										});
									}
									return pluck(df, [
										"label",
										"fieldname",
										"fieldtype",
										"options",
										"table_columns",
										"html",
										"field_template",
									]);
								});
							return column;
						});
						return section;
					});

				this.print_format.format_data = JSON.stringify(this.layout);

				frappe
					.call("frappe.client.save", {
						doc: this.print_format,
					})
					.then(() => {
						if (this.letterhead && this.letterhead._dirty) {
							return frappe
								.call("frappe.client.save", {
									doc: this.letterhead,
								})
								.then((r) => (this.letterhead = r.message));
						}
					})
					.then(() => this.fetch())
					.always(() => {
						frappe.dom.unfreeze();
						this.$emit("after_save");
					});
			},
			reset_changes() {
				this.fetch();
			},
			get_layout() {
				if (this.print_format) {
					if (typeof this.print_format.format_data == "string") {
						return JSON.parse(this.print_format.format_data);
					}
					return this.print_format.format_data;
				}
				return null;
			},
			get_default_layout() {
				return create_default_layout(this.meta, this.print_format);
			},
			change_letterhead(letterhead) {
				return frappe.db.get_doc("Letter Head", letterhead).then((doc) => {
					this.letterhead = doc;
				});
			},
		},
	};
	stores[print_format_name] = new Vue(options);
	return stores[print_format_name];
}

export let storeMixin = {
	inject: ["$store"],
	computed: {
		print_format() {
			return this.$store.print_format;
		},
		layout() {
			return this.$store.layout;
		},
		letterhead() {
			return this.$store.letterhead;
		},
		meta() {
			return this.$store.meta;
		},
	},
};
