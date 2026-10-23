frappe.ui.form.ControlVueComponent = class ControlVueComponent extends frappe.ui.form.Control {
	make() {
		super.make();
		if (this.frm) {
			const update = frappe.utils.debounce(() => this.island?.update(this.get_props()), 300);
			const event = `dirty.vue_component_${this.df.fieldname}`;
			$(this.frm.wrapper).off(event).on(event, update);
		}
	}

	refresh_input() {
		if (!this.df.options || !this.get_doc()) return;

		if (this.island) {
			this.island.update(this.get_props());
			return;
		}

		this.island = frappe.ui.mount_island(this.df.options, this.wrapper, this.get_props());
		this.island.ready.catch((error) => {
			console.error(error);
			this.island = null;
			this.render_unavailable();
		});
	}

	get_props() {
		const doc = this.get_doc();
		return {
			doctype: doc.doctype,
			name: doc.__islocal ? null : doc.name,
			doc: JSON.parse(JSON.stringify(doc)),
			is_new: Boolean(doc.__islocal),
			read_only: this.disp_status !== "Write",
		};
	}

	get_doc() {
		return this.doc || this.frm?.doc;
	}

	render_unavailable() {
		$('<div class="vue-component-unavailable"></div>')
			.text(__('"{0}" is not available on this site.', [this.df.options]))
			.appendTo(this.$wrapper.empty());
	}
};
