import PrintFormatBuilderComponent from "./PrintFormatBuilder.vue";

class PrintFormatBuilder {
	constructor({ wrapper, page, print_format }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.print_format = print_format;

		this.page.clear_actions()
		this.page.clear_custom_actions()

		this.page.set_title(__("Editing {0}", [this.print_format]));
		this.page.set_primary_action(__("Save changes"), () => {
			this.$component.$store.save_changes();
		});
		this.page.set_secondary_action(__("Reset changes"), () => {
			this.$component.$store.reset_changes();
		});
		this.page.add_button(
			__("Preview"),
			() => {
				this.preview();
			},
			{ icon: "small-file" }
		);

		let $vm = new Vue({
			el: this.$wrapper.get(0),
			render: h =>
				h(PrintFormatBuilderComponent, {
					props: {
						print_format_name: print_format
					}
				})
		});
		this.$component = $vm.$children[0];
	}

	async preview() {
		let doctype = this.$component.$store.print_format.doc_type;
		let default_doc = await frappe.db.get_list(doctype, {
			limit: 1
		});

		let d = new frappe.ui.Dialog({
			title: __("Preview Print Format"),
			fields: [
				{
					label: __("Type"),
					fieldname: "type",
					fieldtype: "Select",
					options: ["PDF", "HTML"],
					default: "PDF"
				},
				{
					label: __("Select Document"),
					fieldname: "docname",
					fieldtype: "Link",
					options: doctype,
					reqd: 1,
					default: default_doc.length > 0 ? default_doc[0].name : null
				}
			],
			primary_action: ({ docname, type }) => {
				let params = new URLSearchParams();
				params.append("doctype", doctype);
				params.append("name", docname);
				params.append("print_format", this.print_format);
				let url =
					type == "PDF"
						? `/api/method/frappe.utils.weasyprint.download_pdf`
						: "/printpreview";
				window.open(`${url}?${params.toString()}`, "_blank");
			}
		});
		d.show();
	}
}

frappe.provide("frappe.ui");
frappe.ui.PrintFormatBuilder = PrintFormatBuilder;
export default PrintFormatBuilder;
