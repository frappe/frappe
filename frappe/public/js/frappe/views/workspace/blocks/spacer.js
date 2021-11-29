import Block from './block.js';
export default class Spacer extends Block {
	static get toolbox() {
		return {
			title: 'Spacer',
			icon: frappe.utils.icon('spacer', 'md')
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor({ data, api, config, readOnly }) {
		super({ data, api, config, readOnly });
		this.col = this.data.col ? this.data.col : "12";
	}

	render() {
		this.wrapper = document.createElement('div');
		if (!this.readOnly) {
			let $spacer = $(`
				<div class="widget-head">
					<div></div>
					<div>Spacer</div>
					<div class="widget-control"></div>
				</div>
			`);
			$spacer.appendTo(this.wrapper);

			this.wrapper.classList.add('widget', 'new-widget');
			this.wrapper.style.minHeight = 50 + 'px';

			let $widget_control = $spacer.find('.widget-control');

			this.add_settings_button();
			// frappe.utils.add_custom_button(
			// 	frappe.utils.icon('dot-horizontal', 'xs'),
			// 	(event) => {
			// 		let evn = event;
			// 		!$('.ce-settings.ce-settings--opened').length &&
			// 		setTimeout(() => {
			// 			this.api.toolbar.toggleBlockSettings();
			// 			var position = $(evn.target).offset();
			// 			$('.ce-settings.ce-settings--opened').offset({
			// 				top: position.top + 25,
			// 				left: position.left - 77
			// 			});
			// 		}, 50);
			// 	},
			// 	"tune-btn",
			// 	`${__('Tune')}`,
			// 	null,
			// 	$widget_control
			// );

			frappe.utils.add_custom_button(
				frappe.utils.icon('drag', 'xs'),
				null,
				"drag-handle",
				`${__('Drag')}`,
				null,
				$widget_control
			);

			// frappe.utils.add_custom_button(
			// 	frappe.utils.icon('delete-active', 'xs'),
			// 	() => this.api.blocks.delete(),
			// 	"delete-spacer",
			// 	`${__('Delete')}`,
			// 	null,
			// 	$widget_control
			// );
		}
		return this.wrapper;
	}

	save() {
		return {
			col: this.get_col()
		};
	}
}