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
		!this.readOnly && this.resizer();
		var e = this.wrapper.closest('.ce-block');
		e.classList.add("col-" + this.get_col());
	}

	resizer(wrapper) {
		if (wrapper) this.wrapper = wrapper;
		this.wrapper.className = this.wrapper.className + ' resizable';
		var resizer = document.createElement('div');
		resizer.className = 'resizer';
		this.wrapper.parentElement.appendChild(resizer);
		resizer.addEventListener('mousedown', init_drag, false);
		let me = this;
		var startX, startWidth;

		function init_drag(e) {
			startX = e.clientX;
			startWidth = this.parentElement.offsetWidth;
			document.documentElement.addEventListener('mousemove', do_drag, false);
			document.documentElement.addEventListener('mouseup', stop_drag, false);
		}
		
		function do_drag(e) {
			$(this).css("cursor", "col-resize");
			$('.widget').css("pointer-events", "none");
			$(me.wrapper.parentElement).find('.resizer').css("border-right", "3px solid var(--gray-400)");
			un_focus();
			if ((startWidth + e.clientX - startX) - startWidth > 60) {
				startX = e.clientX;
				me.increase_width();
			} else if ((startWidth + e.clientX - startX) - startWidth < -60) {
				startX = e.clientX;
				me.decrease_width();
			}
		}

		// disable text selection on mousedown (on drag)
		function un_focus() {
			if (document.selection) {
				document.selection.empty();
			} else {
				window.getSelection().removeAllRanges();
			}
		} 

		function stop_drag() {
			$(this).css("cursor", "default");
			$('.widget').css("pointer-events", "auto");
			$(me.wrapper.parentElement).find('.resizer').css("border-right", "0px solid transparent");

			document.documentElement.removeEventListener('mousemove', do_drag, false);
			document.documentElement.removeEventListener('mouseup', stop_drag, false);
		}
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
				$(this.wrapper).find('.widget').addClass(`${widget_type} edit-mode`);
				this.new_block_widget = this.block_widget.get_config();
				this.add_settings_button();
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

	add_new_block_button() {
		let $new_button = $(`
			<div class="new-block-button">${frappe.utils.icon('add-round', 'lg')}</div>
		`);

		$new_button.appendTo(this.wrapper);

		$new_button.click(event => {
			event.stopPropagation();
			let index = this.api.blocks.getCurrentBlockIndex() + 1;
			this.api.blocks.insert('paragraph', {}, {}, index);
			this.api.caret.setToBlock(index);
		});
	}

	add_settings_button() {
		this.dropdown_list = [
			{
				label: 'Delete',
				title: 'Delete Block',
				icon: frappe.utils.icon('delete-active', 'sm'),
				action: () => this.api.blocks.delete()
			},
			{
				label: 'Expand',
				title: 'Expand Block',
				icon: frappe.utils.icon('expand-alt', 'sm'),
				action: () => this.increase_width()
			},
			{
				label: 'Shrink',
				title: 'Shrink Block',
				icon: frappe.utils.icon('shrink', 'sm'),
				action: () => this.decrease_width()
			},
			{
				label: 'Move Up',
				title: 'Move Up',
				icon: frappe.utils.icon('up-arrow', 'sm'),
				action: () => this.move_block('up')
			},
			{
				label: 'Move Down',
				title: 'Move Down',
				icon: frappe.utils.icon('down-arrow', 'sm'),
				action: () => this.move_block('down')
			}
		];

		let $widget_control = $(this.wrapper).find('.widget-control');

		let $button = $(`
			<div class="dropdown-btn">
				<button class="btn btn-secondary btn-xs setting-btn" title="${__('Setting')}">
					${frappe.utils.icon('dot-horizontal', 'xs')}
				</button>
				<div class="dropdown-list hidden"></div>
			</div>
		`);


		let dropdown_item = function(label, title, icon, action) {
			let html = $(`
				<div class="dropdown-item" title="${title}">
					<span class="dropdown-item-icon">${icon}</span>
					<span class="dropdown-item-label">${label}</span>
				</div>
			`);

			html.click(event => {
				event.stopPropagation();
				action && action();
			});

			return html;
		};

		$button.click(event => {
			event.stopPropagation();
			$button.find('.dropdown-list').toggleClass('hidden');
		});

		$(document).click(() => {
			$button.find('.dropdown-list').addClass('hidden');
		});

		$widget_control.prepend($button);

		this.dropdown_list.forEach((item) => {
			$button.find('.dropdown-list').append(dropdown_item(item.label, item.title, item.icon, item.action));
		});
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
		let col = this.col || 12;
		let class_name = "col-12";
		let wrapper = this.wrapper.closest('.ce-block');
		const col_class = new RegExp(/\bcol-.+?\b/, "g");
		if (wrapper && wrapper.className.match(col_class)) {
			wrapper.classList.forEach(function (cn) {
				cn.match(col_class) && (class_name = cn);
			});
			let parts = class_name.split("-");
			col = parseInt(parts[1]);
		}
		return col;
	}

	decrease_width() {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		let currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		let currentBlockElement = currentBlock.holder;

		let className = 'col-12';
		let colClass = new RegExp(/\bcol-.+?\b/, 'g');
		if (currentBlockElement.className.match(colClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(colClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let width = parseInt(parts[1]);
			if (width >= 4) {
				currentBlockElement.classList.remove('col-'+width);
				width = width - 1;
				currentBlockElement.classList.add('col-'+width);
			}
		}
	}

	increase_width() {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		let className = 'col-12';
		const colClass = new RegExp(/\bcol-.+?\b/, 'g');
		if (currentBlockElement.className.match(colClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(colClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let width = parseInt(parts[1]);
			if (width <= 11) {
				currentBlockElement.classList.remove('col-'+width);
				width = width + 1;
				currentBlockElement.classList.add('col-'+width);
			}
		}
	}

	move_block(direction) {
		let current_index = this.api.blocks.getCurrentBlockIndex();
		let new_index = current_index + (direction == 'down' ? 1 : -1);
		this.api.blocks.move(new_index, current_index);
	}
}