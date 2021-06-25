frappe.provide('frappe.ui.form');
frappe.provide('frappe.success_action');

frappe.ui.form.SuccessAction = class SuccessAction {
	constructor(form) {
		this.form = form;
		this.load_setting();
	}

	load_setting() {
		this.setting = frappe.boot.success_action
			.find(setting => setting.ref_doctype === this.form.doctype);
	}

	show() {
		if (!this.setting) return;
		if (this.form.doc.docstatus === 0 && !this.is_first_creation()) return;

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
		frappe.db.get_list(this.form.doctype, {limit: 2})
			.then(result => {
				const count = result.length;
				const setting = this.setting;
				let message = count === 1 ?
					setting.first_success_message :
					setting.message;

				const $buttons = this.get_actions().map(action => {
					const $btn = $(`<button class="next-action"><span>${__(action.label)}</span></button>`);
					$btn.click(() => action.action(this.form));
					return $btn;
				});

				const next_action_container = $(`<div class="next-action-container"></div>`);
				next_action_container.append($buttons);
				const html = next_action_container;

				frappe.show_alert({
					message: message,
					body: html,
					indicator: 'green',
				}, setting.action_timeout || 7);
			});
	}

	get_actions() {
		const actions = [];
		const checked_actions = this.setting.next_actions.split("\n");
		checked_actions
			.forEach(action => {
				if (typeof action === 'string' && this.default_actions[action]) {
					actions.push(this.default_actions[action]);
				} else if (typeof action === 'object') {
					actions.push(action);
				}
			});

		return actions;
	}

	get default_actions() {
		return {
			'new': {
				label: __('New'),
				action: (frm) => frappe.new_doc(frm.doctype)
			},
			'print': {
				label: __('Print'),
				action: (frm) => frm.print_doc()
			},
			'email': {
				label: __('Email'),
				action: (frm) => frm.email_doc()
			},
			'list': {
				label: __('View All'),
				action: (frm) => {
					frappe.set_route('List', frm.doctype);
				}
			}
		};
	}

	is_first_creation() {
		let { modified, creation } = this.form.doc;

		// strip out milliseconds
		modified = modified.split('.')[0];
		creation = creation.split('.')[0];

		return modified === creation;
	}

};
