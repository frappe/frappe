frappe.ModuleEditor = class ModuleEditor {
	constructor(frm, wrapper, disable) {
		this.frm = frm;
		this.wrapper = wrapper;
		this.disable = disable;
		const block_modules = this.frm.doc.block_modules.map((row) => row.module);
		this.multicheck = frappe.ui.form.make_control({
			parent: wrapper,
			df: {
				fieldname: "block_modules",
				fieldtype: "MultiCheck",
				select_all: true,
				columns: "15rem",
				get_data: () => {
					return this.frm.doc.__onload.all_modules.map((module) => {
						return {
							label: __(module),
							value: module,
							checked: !block_modules.includes(module),
						};
					});
				},
				on_change: () => {
					this.set_modules_in_table();
					this.frm.dirty();
				},
			},
			render_input: true,
		});
	}
	set_enable_disable() {
		$(this.wrapper)
			.find('input[type="checkbox"]')
			.attr("disabled", this.disable ? true : false);
	}

	show() {
		const block_modules = this.frm.doc.block_modules.map((row) => row.module);
		const all_modules = this.frm.doc.__onload.all_modules;
		this.multicheck.selected_options = all_modules.filter((m) => !block_modules.includes(m));
		this.multicheck.refresh_input();
		this.set_enable_disable();
	}

	set_modules_in_table() {
		let block_modules = this.frm.doc.block_modules || [];
		let unchecked_options = this.multicheck.get_unchecked_options();

		block_modules.map((module_doc) => {
			if (!unchecked_options.includes(module_doc.module)) {
				frappe.model.clear_doc(module_doc.doctype, module_doc.name);
			}
		});

		unchecked_options.map((module) => {
			if (!block_modules.find((d) => d.module === module)) {
				let module_doc = frappe.model.add_child(
					this.frm.doc,
					"Block Module",
					"block_modules"
				);
				module_doc.module = module;
			}
		});
	}
};
