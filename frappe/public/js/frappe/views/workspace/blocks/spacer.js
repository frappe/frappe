import Block from './block.js';
export default class Spacer extends Block {
	static get toolbox() {
		return {
			title: 'Spacer',
			icon: '<svg width="18" height="18" viewBox="0 0 400 400"><path d="M377.87 24.126C361.786 8.042 342.417 0 319.769 0H82.227C59.579 0 40.211 8.042 24.125 24.126 8.044 40.212.002 59.576.002 82.228v237.543c0 22.647 8.042 42.014 24.123 58.101 16.086 16.085 35.454 24.127 58.102 24.127h237.542c22.648 0 42.011-8.042 58.102-24.127 16.085-16.087 24.126-35.453 24.126-58.101V82.228c-.004-22.648-8.046-42.016-24.127-58.102zm-12.422 295.645c0 12.559-4.47 23.314-13.415 32.264-8.945 8.945-19.698 13.411-32.265 13.411H82.227c-12.563 0-23.317-4.466-32.264-13.411-8.945-8.949-13.418-19.705-13.418-32.264V82.228c0-12.562 4.473-23.316 13.418-32.264 8.947-8.946 19.701-13.418 32.264-13.418h237.542c12.566 0 23.319 4.473 32.265 13.418 8.945 8.947 13.415 19.701 13.415 32.264v237.543h-.001z"/></svg>'
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
				$widget_control
			);

			frappe.utils.add_custom_button(
				frappe.utils.icon('drag', 'xs'),
				null,
				"drag-handle",
				`${__('Drag')}`,
				null,
				$widget_control
			);

			frappe.utils.add_custom_button(
				frappe.utils.icon('delete', 'xs'),
				() => this.api.blocks.delete(),
				"delete-spacer",
				`${__('Delete')}`,
				null,
				$widget_control
			);
		}
		return this.wrapper;
	}

	save() {
		return {
			col: this.get_col()
		};
	}
}