export default class SpacingTune {
	static get isTune() {
		return true;
	}

	constructor({api, settings}) {
		this.api = api;
		this.settings = settings;
		this.CSS = {
			button: 'ce-settings__button',
			wrapper: 'ce-tune-layout',
			sidebar: 'cdx-settings-sidebar',
			animation: 'wobble',
		};
		this.data = { colWidth: 12 };
		this.wrapper = undefined;
		this.sidebar = undefined;
	}

	render() {
		let me = this;
		let layoutWrapper = document.createElement('div');
		layoutWrapper.classList.add(this.CSS.wrapper);
		let decreaseWidthButton = document.createElement('div');
		decreaseWidthButton.classList.add(this.CSS.button, 'ce-shrink-button');
		let increaseWidthButton = document.createElement('div');
		increaseWidthButton.classList.add(this.CSS.button, 'ce-expand-button');

		layoutWrapper.appendChild(decreaseWidthButton);
		layoutWrapper.appendChild(increaseWidthButton);

		decreaseWidthButton.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 380 17 10" style="enable-background:new -674 380 17 10;" xml:space="preserve"><path d="M-674,383.9h3.6l-1.7-1.7c-0.4-0.4-0.4-1.2,0-1.6c0.4-0.4,1.1-0.4,1.6,0l3.2,3.2c0.6,0.2,0.8,0.8,0.6,1.4	c-0.1,0.1-0.1,0.3-0.2,0.4l-3.8,3.8c-0.4,0.4-1.1,0.4-1.5,0c-0.4-0.4-0.4-1.1,0-1.5l1.8-1.8h-3.6V383.9z"/><path d="M-657,386.1h-3.6l1.7,1.7c0.4,0.4,0.4,1.2,0,1.6c-0.4,0.4-1.1,0.4-1.6,0l-3.2-3.2c-0.6-0.2-0.8-0.8-0.6-1.4	c0.1-0.1,0.1-0.3,0.2-0.4l3.8-3.8c0.4-0.4,1.1-0.4,1.5,0c0.4,0.4,0.4,1.1,0,1.5l-1.8,1.8h3.6V386.1z"/></svg>`;
		this.api.tooltip.onHover(decreaseWidthButton, 'Shrink', {
			placement: 'top',
			hidingDelay: 500,
		});
		this.api.listeners.on(
			decreaseWidthButton,
			'click',
			() => me.decreaseWidth(),
			false
		);

		increaseWidthButton.innerHTML = `<svg width="17" height="10" viewBox="0 0 17 10"><path d="M13.568 5.925H4.056l1.703 1.703a1.125 1.125 0 0 1-1.59 1.591L.962 6.014A1.069 1.069 0 0 1 .588 4.26L4.38.469a1.069 1.069 0 0 1 1.512 1.511L4.084 3.787h9.606l-1.85-1.85a1.069 1.069 0 1 1 1.512-1.51l3.792 3.791a1.069 1.069 0 0 1-.475 1.788L13.514 9.16a1.125 1.125 0 0 1-1.59-1.591l1.644-1.644z"/></svg>`;
		this.api.tooltip.onHover(increaseWidthButton, 'Expand', {
			placement: 'top',
			hidingDelay: 500,
		});
		this.api.listeners.on(
			increaseWidthButton,
			'click',
			() => me.increaseWidth(),
			false
		);

		this.wrapper = layoutWrapper;
		return layoutWrapper;
	}

	decreaseWidth() {
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

	increaseWidth() {
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
}