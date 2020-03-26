const WIDGET_DOCTYPE_MAP = {
	chart: "Desk Chart",
	shortcut: "Desk Shortcut",
}

export default class NewWidget {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	refresh() {
		//
	}

	customize() {
		return
	}

	make() {
		this.make_widget();
		this.widget.appendTo(this.container);
		this.setup_events();
	}

	get_title() {
		return __(`New ${frappe.utils.to_title_case(this.type)}`)
	}

	make_widget() {
		this.widget = $(`<div class="widget new-widget">
				+ ${this.get_title()}
			</div>`);
		this.body = this.widget
	}

	setup_events() {
		this.widget.on('click', () => this.open_dialog())
	}

	delete() {
		this.widget.remove();
	}

	open_dialog() {
		let doctype = WIDGET_DOCTYPE_MAP[this.type]

		if (!doctype) {
			console.log(`Could not find ${this.type}`)
		}

		frappe.model.with_doctype(doctype, () => {
			let new_dialog = new frappe.ui.Dialog({
				title: this.get_title(),
				fields: frappe.get_meta(doctype).fields,
				primary_action: (data) => {
					if (this.type == 'chart' && !data.label) {
						data.label = data.chart_name;
					}

					if (this.type == 'shortcut') {
						data.label = data.link_to;
					}

					data.docname = frappe.utils.get_random(20);

					new_dialog.hide();
					this.on_create(data);
				},
				primary_action_label: __("Add"),
			});

			new_dialog.show()
		});
	}
}