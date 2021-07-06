import get_dialog_constructor from "../../../widgets/widget_dialog.js";

export default class Block {
	constructor(opts) {
		Object.assign(this, opts);
	}

	make(block, block_name, widget_type = block) {
		let block_data = this.config.page_data[block+'s'].items.find(obj => {
			return obj.label == block_name;
		});
		if (!block_data) return false;
		this.wrapper.innerHTML = '';
		block_data.in_customize_mode = !this.readOnly;
		this.block_widget = new frappe.widget.SingleWidgetGroup({
			container: this.wrapper,
			type: widget_type,
			class_name: block == 'chart' ? 'widget-charts' : '',
			options: this.options,
			widgets: block_data,
			api: this.api,
			block: this.block
		});
		this.wrapper.setAttribute(block+'_name', block_name);
		if (!this.readOnly) {
			this.block_widget.customize();
		}
		return true;
	}

	rendered() {
		var e = this.wrapper.closest('.ce-block');
		e.classList.add("col-" + this.col);
		e.classList.add("pt-" + this.pt);
		e.classList.add("pr-" + this.pr);
		e.classList.add("pb-" + this.pb);
		e.classList.add("pl-" + this.pl);
	}

	new(block, widget_type = block) {
		const dialog_class = get_dialog_constructor(widget_type);
		let block_name = block+'_name';
		this.dialog = new dialog_class({
			label: this.label,
			type: widget_type,
			primary_action: (widget) => {
				widget.in_customize_mode = 1;
				this.block_widget = frappe.widget.make_widget({
					...widget,
					widget_type: widget_type,
					container: this.wrapper,
					options: {
						...this.options,
						on_delete: () => this.api.blocks.delete(),
						on_edit: () => this.on_edit(this.block_widget)
					}
				});
				this.block_widget.customize(this.options);
				this.wrapper.setAttribute(block_name, this.block_widget.label);
				this.new_block_widget = this.block_widget.get_config();
				this.add_tune_button();
			},
		});

		if (!this.readOnly && this.data && !this.data[block_name]) {
			this.dialog.make();
		}
	}

	on_edit(block_obj) {
		let block_name = block_obj.edit_dialog.type+'_name';
		if (block_obj.edit_dialog.type == 'links') {
			block_name = 'card_name';
		}
		let block = block_obj.get_config();
		this.block_widget.widgets = block;
		this.wrapper.setAttribute(block_name, block.label);
		this.new_block_widget = block_obj.get_config();
	}

	add_tune_button() {
		let $widget_control = $(this.wrapper).find('.widget-control');
		frappe.utils.add_custom_button(
			frappe.utils.icon('dot-horizontal', 'xs'),
			(event) => {
				let evn = event;
				!$('.ce-settings.ce-settings--opened').length &&
				setTimeout(() => {
					this.api.toolbar.toggleBlockSettings();
					var position = $(evn.target).offset();
					$('.ce-settings.ce-settings--opened').offset({
						top: position.top + 25,
						left: position.left - 77
					});
				}, 50);
			},
			"tune-btn",
			`${__('Tune')}`,
			null,
			$widget_control,
			true
		);
	}

	get_col() {
		let col = 12;
		let class_name = "col-12";
		let wrapper = this.wrapper.closest('.ce-block');
		const col_class = new RegExp(/\bcol-.+?\b/, "g");
		if (wrapper.className.match(col_class)) {
			wrapper.classList.forEach(function (cn) {
				cn.match(col_class) && (class_name = cn);
			});
			let parts = class_name.split("-");
			col = parseInt(parts[1]);
		}
		return col;
	}

	get_padding() {
		let direction = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : "l";
		let padding = 0;
		let pad_name = "p" + direction + "-0";
		let wrapper = this.wrapper.closest('.ce-block');
		let pad_left = new RegExp(/\pl-.+?\b/, "g");
		let pad_right = new RegExp(/\pr-.+?\b/, "g");
		let pad_top = new RegExp(/\pt-.+?\b/, "g");
		let pad_bottom = new RegExp(/\pb-.+?\b/, "g");

		const get_padding = (pad_direction) => {
			if (wrapper.className.match(pad_direction)) {
				wrapper.classList.forEach(function (cn) {
					cn.match(pad_direction) && (pad_name = cn);
				});
				let parts = pad_name.split("-");
				padding = parseInt(parts[1]);
			}
		};

		if ("l" == direction) {
			get_padding(pad_left);
		} else if ("r" == direction) {
			get_padding(pad_right);
		} else if ("t" == direction) {
			get_padding(pad_top);
		} else if ("b" == direction) {
			get_padding(pad_bottom);
		}
		return padding;
	}
}