<template>
	<div class="layout-main-section row" v-if="print_format && meta && layout">
		<div class="col-3">
			<PrintFormatControls
				:print_format="print_format"
				:meta="meta"
				@update="update($event)"
			/>
		</div>
		<div class="print-format-container col-9">
			<PrintFormat :print_format="print_format" :meta="meta" :layout="layout" />
		</div>
	</div>
</template>

<script>
import PrintFormat from "./PrintFormat.vue";
import PrintFormatControls from "./PrintFormatControls.vue";
import { create_default_layout } from "./utils";

export default {
	name: "PrintFormatBuilder",
	props: ["print_format_name"],
	components: {
		PrintFormat,
		PrintFormatControls,
	},
	data() {
		return {
			print_format: null,
			doctype: null,
			meta: null,
			layout: null,
		};
	},
	mounted() {
		this.fetch();
	},
	methods: {
		fetch() {
			frappe.dom.freeze(__("Loading..."));
			frappe.model.clear_doc("Print Format", this.print_format_name);
			frappe.model.with_doc("Print Format", this.print_format_name, () => {
				this.print_format = frappe.get_doc(
					"Print Format",
					this.print_format_name
				);
				frappe.model.with_doctype(this.print_format.doc_type, () => {
					this.meta = frappe.get_meta(this.print_format.doc_type);
					this.layout = this.get_layout();
					frappe.dom.unfreeze();
				});
			});
		},
		update({ fieldname, value }) {
			this.$set(this.print_format, fieldname, value);
		},
		save_changes() {
			frappe.dom.freeze();

			this.layout.sections = this.layout.sections
				.map((section) => {
					section.columns = section.columns.map((column) => {
						column.fields = column.fields.filter((df) => !df.remove);
						return column;
					});
					return section.remove ? null : section;
				})
				.filter(Boolean);

			this.print_format.format_data = JSON.stringify(this.layout);

			frappe
				.call("frappe.client.save", {
					doc: this.print_format,
				})
				.then(() => {
					this.fetch();
				})
				.always(() => {
					frappe.dom.unfreeze();
				});
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
		},
	},
};
</script>

<style scoped>
.print-format-container {
	height: calc(100vh - 140px);
	overflow-y: auto;
	padding-top: 0.5rem;
	padding-bottom: 4rem;
}
</style>