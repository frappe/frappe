
import './field_group';
import '../dom';

frappe.provide('frappe.ui');

window.cur_dialog = null;

frappe.ui.open_dialogs = [];

frappe.ui.Dialog = class Dialog extends frappe.ui.FieldGroup {
	constructor(opts) {
		super();
		this.display = false;
		this.is_dialog = true;

		$.extend(this, { animate: true, size: null }, opts);
		this.make();
	}

	make() {
		this.$wrapper = frappe.get_modal("", "");

		if(this.static) {
			this.$wrapper.modal({
				backdrop: 'static',
				keyboard: false
			});
			this.get_close_btn().hide();
		}

		this.wrapper = this.$wrapper.find('.modal-dialog')
			.get(0);
		if (this.size == "small" )
			$(this.wrapper).addClass("modal-sm");
		else if (this.size == "large" )
			$(this.wrapper).addClass("modal-lg");
		else if (this.size == "extra-large" )
			$(this.wrapper).addClass("modal-xl");

		this.make_head();
		this.modal_body = this.$wrapper.find(".modal-body");
		this.$body = $('<div></div>').appendTo(this.modal_body);
		this.body = this.$body.get(0);
		this.$message = $('<div class="hide modal-message"></div>').appendTo(this.modal_body);
		this.header = this.$wrapper.find(".modal-header");
		this.footer = this.$wrapper.find(".modal-footer");
		this.standard_actions = this.footer.find('.standard-actions');
		this.custom_actions = this.footer.find('.custom-actions');
		this.set_indicator();

		// make fields (if any)
		super.make();

		this.refresh_section_collapse();

		// show footer
		this.action = this.action || { primary: { }, secondary: { } };
		if (this.primary_action || (this.action.primary && this.action.primary.onsubmit)) {
			this.set_primary_action(this.primary_action_label || this.action.primary.label || __("Submit"),
				this.primary_action || this.action.primary.onsubmit);
		}

		if (this.secondary_action) {
			this.set_secondary_action(this.secondary_action);
		}

		if (this.secondary_action_label || (this.action.secondary && this.action.secondary.label)) {
			this.set_secondary_action_label(this.secondary_action_label || this.action.secondary.label);
		}

		if (this.minimizable) {
			this.header.find('.title-section').click(() => this.is_minimized && this.toggle_minimize());
			this.get_minimize_btn().removeClass('hide').on('click', () => this.toggle_minimize());
		}

		var me = this;
		this.$wrapper
			.on("hide.bs.modal", function() {
				me.display = false;

				if(frappe.ui.open_dialogs[frappe.ui.open_dialogs.length-1]===me) {
					frappe.ui.open_dialogs.pop();
					if(frappe.ui.open_dialogs.length) {
						window.cur_dialog = frappe.ui.open_dialogs[frappe.ui.open_dialogs.length-1];
					} else {
						window.cur_dialog = null;
					}
				}
				me.onhide && me.onhide();
				me.on_hide && me.on_hide();
			})
			.on("shown.bs.modal", function() {
				// focus on first input
				me.display = true;
				window.cur_dialog = me;
				frappe.ui.open_dialogs.push(me);
				me.focus_on_first_input();
				me.on_page_show && me.on_page_show();
				$(document).trigger('frappe.ui.Dialog:shown');
			})
			.on('scroll', function() {
				var $input = $('input:focus');
				if ($input.length && ['Date', 'Datetime', 'Time'].includes($input.attr('data-fieldtype'))) {
					$input.blur();
				}
			});

	}

	get_primary_btn() {
		return this.standard_actions.find(".btn-primary");
	}

	get_minimize_btn() {
		return this.$wrapper.find(".modal-header .btn-modal-minimize");
	}

	set_message(text) {
		this.$message.removeClass('hide');
		this.$body.addClass('hide');
		this.$message.text(text);
	}

	clear_message() {
		this.$message.addClass('hide');
		this.$body.removeClass('hide');
	}

	clear() {
		super.clear();
		this.clear_message();
	}

	set_primary_action(label, click) {
		this.footer.removeClass('hide');
		this.has_primary_action = true;
		var me = this;
		return this.get_primary_btn()
			.removeClass("hide")
			.html(label)
			.click(function() {
				me.primary_action_fulfilled = true;
				// get values and send it
				// as first parameter to click callback
				// if no values then return
				var values = me.get_values();
				if(!values) return;
				click && click.apply(me, [values]);
			});
	}

	set_secondary_action(click) {
		this.footer.removeClass('hide');
		this.get_secondary_btn().removeClass('hide').on('click', click);
	}

	set_secondary_action_label(label) {
		this.get_secondary_btn()
			.removeClass("hide")
			.html(label);
	}

	disable_primary_action() {
		this.get_primary_btn().addClass('disabled');
	}

	enable_primary_action() {
		this.get_primary_btn().removeClass('disabled');
	}

	make_head() {
		this.set_title(this.title);
	}

	set_title(t) {
		this.$wrapper.find(".modal-title").html(t);
	}

	set_indicator() {
		if (this.indicator) {
			this.header.find('.indicator').removeClass().addClass('indicator ' + this.indicator);
		}
	}

	show() {
		// show it
		if (this.animate) {
			this.$wrapper.addClass('fade');
		} else {
			this.$wrapper.removeClass('fade');
		}
		this.$wrapper.modal("show");

		this.$wrapper.removeClass('modal-minimize');

		// clear any message
		this.clear_message();

		this.primary_action_fulfilled = false;
		this.is_visible = true;
		return this;
	}

	hide() {
		this.$wrapper.modal("hide");
		this.is_visible = false;
	}

	get_close_btn() {
		return this.$wrapper.find(".btn-modal-close");
	}

	get_secondary_btn() {
		return this.standard_actions.find(".btn-modal-secondary");
	}

	no_cancel() {
		this.get_close_btn().toggle(false);
	}

	cancel() {
		this.get_close_btn().trigger("click");
	}

	toggle_minimize() {
		$('.modal-backdrop').toggle();
		let modal = this.$wrapper.closest('.modal').toggleClass('modal-minimize');
		modal.attr('tabindex') ? modal.removeAttr('tabindex') : modal.attr('tabindex', -1);
		this.is_minimized = !this.is_minimized;
		const icon = this.is_minimized ? 'expand' : 'collapse';
		this.get_minimize_btn().html(frappe.utils.icon(icon));
		this.on_minimize_toggle && this.on_minimize_toggle(this.is_minimized);
		this.header.find('.modal-title').toggleClass('cursor-pointer');
	}

	add_custom_action(label, action, css_class=null) {
		this.footer.removeClass('hide');
		let action_button = $(`
			<button class="btn btn-secondary btn-sm ${css_class || ''}">
				${label}
			</button>
		`);
		this.custom_actions.append(action_button);

		action && action_button.click(action);
	}
};

frappe.ui.hide_open_dialog = () => {
	// hide open dialog
	if (window.cur_dialog) {
		if (!cur_dialog.minimizable) {
			cur_dialog.hide();
		} else if (!cur_dialog.is_minimized) {
			cur_dialog.toggle_minimize();
		}
	}
};
