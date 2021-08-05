import Picker from '../../icon_picker/icon_picker';

frappe.ui.form.ControlIcon = class ControlIcon extends frappe.ui.form.ControlData {
	make_input() {
		this.df.placeholder = this.df.placeholder || __('Choose an icon');
		super.make_input();
		this.get_all_icons();
		this.make_icon_input();
	}

	get_all_icons() {
		frappe.symbols = [];
		$("#frappe-symbols > symbol[id]").each(function() {
			frappe.symbols.push(this.id.replace('icon-', ''));
		});
	}

	make_icon_input() {
		let picker_wrapper = $('<div>');
		this.picker = new Picker({
			parent: picker_wrapper,
			icon: this.get_icon(),
			icons: frappe.symbols
		});

		this.$wrapper.popover({
			trigger: 'manual',
			offset: `${-this.$wrapper.width() / 4.5}, 5`,
			boundary: 'viewport',
			placement: 'bottom',
			template: `
				<div class="popover icon-picker-popover">
					<div class="picker-arrow arrow"></div>
					<div class="popover-body popover-content"></div>
				</div>
			`,
			content: () => picker_wrapper,
			html: true
		}).on('show.bs.popover', () => {
			setTimeout(() => {
				this.picker.refresh();
			}, 10);
		}).on('hidden.bs.popover', () => {
			$('body').off('click.icon-popover');
			$(window).off('hashchange.icon-popover');
		});

		this.picker.on_change = (icon) => {
			this.set_value(icon);
		};

		if (!this.selected_icon) {
			this.selected_icon = $(`<div class="selected-icon">${frappe.utils.icon("folder-normal", "md")}</div>`);
			this.selected_icon.insertAfter(this.$input);
		}

		this.$wrapper.find('.selected-icon').parent().on('click', (e) => {
			this.$wrapper.popover('toggle');
			if (!this.get_icon()) {
				this.$input.val('');
			}
			e.stopPropagation();
			$('body').on('click.icon-popover', (ev) => {
				if (!$(ev.target).parents().is('.popover')) {
					this.$wrapper.popover('hide');
				}
			});
			$(window).on('hashchange.icon-popover', () => {
				this.$wrapper.popover('hide');
			});
		});
	}

	refresh() {
		super.refresh();
		let icon = this.get_icon();
		if (this.picker && this.picker.icon !== icon) {
			this.picker.icon = icon;
			this.picker.refresh();
		}
	}

	set_formatted_input(value) {
		super.set_formatted_input(value);
		this.$input.val(value);
		this.selected_icon.find("use").attr("href", "#icon-"+(value || "folder-normal"));
		this.selected_icon.toggleClass('no-value', !value);
	}

	get_icon() {
		return this.get_value() || 'folder-normal';
	}
};
