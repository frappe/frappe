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

	make_dom() {
		this.container = $(document.body).find('.success-container');
		const nav_z_index = $(document.body).find('.navbar-fixed-top').css('z-index');
		if (!this.container.length) {
			this.container = $('<div class="success-container">').appendTo(document.body);
		}

		const $buttons = this.config.actions.map(action => {
			const $btn = $(`<button class="next-action-button text-muted"><i class="${action.icon}"></i> <span>${action.label}</span></button> `);
			$btn.click(() => action.action(this.form));
			return $btn;
		});

		this.wrapper = $(`
			<div class="success-action border">
				<i class="success-icon fa fa-check-circle"></i>
				<h2 class="success-message">Success</h2>
				<p class="success-description">${this.config.message}</>
				<div class="actions"></div>
			</div>
		`).appendTo(this.container);

		this.wrapper.find('.actions').append($buttons);
		this.container.css('z-index', nav_z_index+1);
		this.container.show().css('right', '20px');
		this.wrapper.delay(4 * 1000).fadeOut('slow');
		// this.wrapper.hover((event) => {
		// 	if (event.type === 'mouseenter') {
		// 		this.wrapper.stop().fadeIn(100);
		// 	} else {
		// 		this.wrapper.stop().delay(2 * 1000).fadeOut('slow');
		// 	}

		// });
	}

	show() {
		if (!this.config) return;
		this.make_dom();
	}
};
