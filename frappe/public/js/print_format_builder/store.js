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
				print_format: null,
				doctype: null,
				meta: null,
				layout: null
			};
		},
		methods: {
			fetch() {
				frappe.model.clear_doc("Print Format", this.print_format_name);
				frappe.model.with_doc(
					"Print Format",
					this.print_format_name,
					() => {
						this.print_format = frappe.get_doc(
							"Print Format",
							this.print_format_name
						);
						frappe.model.with_doctype(
							this.print_format.doc_type,
							() => {
								this.meta = frappe.get_meta(
									this.print_format.doc_type
								);
								this.layout = this.get_layout();
							}
						);
					}
				);
			},
			update({ fieldname, value }) {
				this.$set(this.print_format, fieldname, value);
			},
			save_changes() {
				frappe.dom.freeze(__("Saving..."));

				this.layout.sections = this.layout.sections
					.filter(section => !section.remove)
					.map(section => {
						section.columns = section.columns.map(column => {
							column.fields = column.fields
								.filter(df => !df.remove)
								.map(df => {
									if (df.table_columns) {
										df.table_columns = df.table_columns.map(
											tf => {
												return pluck(tf, [
													"label",
													"fieldname",
													"fieldtype",
													"options",
													"width"
												]);
											}
										);
									}
									return pluck(df, [
										"label",
										"fieldname",
										"fieldtype",
										"options",
										"table_columns",
										"html"
									]);
								});
							return column;
						});
						return section;
					});

				this.print_format.format_data = JSON.stringify(this.layout);

				frappe
					.call("frappe.client.save", {
						doc: this.print_format
					})
					.then(() => this.fetch())
					.always(() => frappe.dom.unfreeze());
			},
			reset_changes() {
				this.fetch();
			},
			get_layout() {
				if (this.print_format) {
					if (!this.print_format.format_data) {
						return create_default_layout(this.meta);
					}
					if (typeof this.print_format.format_data == "string") {
						return JSON.parse(this.print_format.format_data);
					}
					return this.print_format.format_data;
				}
				return null;
			}
		}
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
		meta() {
			return this.$store.meta;
		}
	}
};
