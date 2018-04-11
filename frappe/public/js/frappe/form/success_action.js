frappe.provide('frappe.ui.form');
frappe.provide('frappe.success_action');

frappe.ui.form.SuccessAction = class SuccessAction {
	constructor(form) {
		this.form = form;
		this.load_config();
	}

	load_config() {
		this.config = frappe.success_action[this.form.doctype] || null;
	}

	show() {
		if (!this.config) return;
		if (this.form.doc.docstatus === 0 && !this.form.is_first_creation()) return;

		this.prepare_dom();
		this.show_alert();
	}

	prepare_dom() {
		this.container = $(document.body).find('.success-container');
		if (!this.container.length) {
			this.container = $('<div class="success-container">').appendTo(document.body);
		}
	}

	show_alert() {
		frappe.db.count(this.form.doctype)
			.then(count => {
				let message = count === 1 ?
					this.config.first_creation_message :
					this.config.message;

				const $buttons = this.get_actions().map(action => {
					const $btn = $(`<button class="next-action"><span>${action.label}</span></button>`);
					$btn.click(() => action.action(this.form));
					return $btn;
				});
				const next_action_container = $(`<div class="next-action-container"></div>`);
				next_action_container.append($buttons);
				const html = next_action_container;

				frappe.show_alert({
					message: message,
					body: html,
					indicator: 'green'
				});
			});
	}

	get_actions() {
		const default_actions = {
			New: {
				label: __('New'),
				action: (frm) => frappe.new_doc(frm.doctype)
			},
			Print: {
				label: __('Print'),
				action: (frm) => frm.print_doc()
			},
			Email: {
				label: __('Email'),
				action: (frm) => frm.email_doc()
			}
		};

		const actions = [];

		this.config.actions
			.forEach(action => {
				if (typeof action === 'string') {
					actions.push(default_actions[action]);
				} else {
					actions.push(action);
				}
			});

		return actions;
	}
};
