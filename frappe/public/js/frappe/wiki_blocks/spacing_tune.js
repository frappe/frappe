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
		this.data = { colWidth: 12, pl: 0, pr: 0, pt: 0, pb: 0 };
		this.wrapper = undefined;
		this.sidebar = undefined;
	}

	render() {
		let me = this;
		let layoutWrapper = document.createElement('div');
		layoutWrapper.classList.add(this.CSS.wrapper);
		let decreaseWidthButton = document.createElement('div');
		decreaseWidthButton.classList.add(this.CSS.button);
		let increaseWidthButton = document.createElement('div');
		increaseWidthButton.classList.add(this.CSS.button);
		let paddingButton = document.createElement('div');
		paddingButton.classList.add(this.CSS.button);

		layoutWrapper.appendChild(paddingButton);
		layoutWrapper.appendChild(decreaseWidthButton);
		layoutWrapper.appendChild(increaseWidthButton);

		// paddingButton.appendChild($.svg('padding', 15, 15));
		paddingButton.innerHTML = `<svg version="1.1" height="12" x="0px" y="0px" viewBox="-674 379 17 12" style="enable-background:new -674 379 17 12;" xml:space="preserve"><rect x="-666.1" y="379.9" width="1.7" height="10.3"/><polygon points="-657,384.2 -659.9,384.2 -658.8,383.1 -660,381.9 -663.1,385 -660,388.1 -658.8,386.9 -659.9,385.8 -657,385.8 "/><rect x="-671.9" y="379.9" width="4.1" height="1.7"/><rect x="-674" y="384.2" width="6.1" height="1.7"/><rect x="-671.9" y="388.4" width="4.1" height="1.7"/></svg>`;
		this.api.listeners.on(
			paddingButton,
			'click',
			(event) => me.showPadding(event, paddingButton),
			false
		);

		// decreaseWidthButton.appendChild($.svg('decrease-width', 15, 15));
		decreaseWidthButton.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 380 17 10" style="enable-background:new -674 380 17 10;" xml:space="preserve"><path d="M-674,383.9h3.6l-1.7-1.7c-0.4-0.4-0.4-1.2,0-1.6c0.4-0.4,1.1-0.4,1.6,0l3.2,3.2c0.6,0.2,0.8,0.8,0.6,1.4	c-0.1,0.1-0.1,0.3-0.2,0.4l-3.8,3.8c-0.4,0.4-1.1,0.4-1.5,0c-0.4-0.4-0.4-1.1,0-1.5l1.8-1.8h-3.6V383.9z"/><path d="M-657,386.1h-3.6l1.7,1.7c0.4,0.4,0.4,1.2,0,1.6c-0.4,0.4-1.1,0.4-1.6,0l-3.2-3.2c-0.6-0.2-0.8-0.8-0.6-1.4	c0.1-0.1,0.1-0.3,0.2-0.4l3.8-3.8c0.4-0.4,1.1-0.4,1.5,0c0.4,0.4,0.4,1.1,0,1.5l-1.8,1.8h3.6V386.1z"/></svg>`;
		this.api.listeners.on(
			decreaseWidthButton,
			'click',
			(event) => me.decreaseWidth(event, decreaseWidthButton),
			false
		);

		// increaseWidthButton.appendChild();
		increaseWidthButton.innerHTML = `<svg width="17" height="10" viewBox="0 0 17 10"><path d="M13.568 5.925H4.056l1.703 1.703a1.125 1.125 0 0 1-1.59 1.591L.962 6.014A1.069 1.069 0 0 1 .588 4.26L4.38.469a1.069 1.069 0 0 1 1.512 1.511L4.084 3.787h9.606l-1.85-1.85a1.069 1.069 0 1 1 1.512-1.51l3.792 3.791a1.069 1.069 0 0 1-.475 1.788L13.514 9.16a1.125 1.125 0 0 1-1.59-1.591l1.644-1.644z"/></svg>`;
		this.api.listeners.on(
			increaseWidthButton,
			'click',
			(event) => me.increaseWidth(event, increaseWidthButton),
			false
		);

		this.wrapper = layoutWrapper;
		return layoutWrapper;
	}

	decreaseWidth(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		let currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		let currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
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
			if (width >= 2) {
				currentBlockElement.classList.remove('col-'+width);
				width = width - 1;
				currentBlockElement.classList.add('col-'+width);
			}
		}
	}

	increaseWidth(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
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
		
	showPadding(event, button) {
		let me = this;
		if (button.classList.contains('cdx-settings-button--active')) {
			this.sidebar.remove();
			button.classList.remove('cdx-settings-button--active');
		} else {
			button.classList.add('cdx-settings-button--active');

			let sidebarWrapper = document.createElement('div');
			sidebarWrapper.classList.add(this.CSS.sidebar);

			let paddingLeftCaption = document.createElement('button');
			paddingLeftCaption.classList.add(this.CSS.button, 'disabled');
			// paddingLeftCaption.appendChild($.svg('arrow-left', 10, 10));
			paddingLeftCaption.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 380 17 10" style="enable-background:new -674 380 17 10;" xml:space="preserve"><polygon points="-659,384.1 -667.8,384.1 -665.8,381.9 -667,380.7 -671,384.9 -667.1,388.9 -665.8,387.7 -667.8,385.7 -659,385.7 	"/></svg>`;

			let paddingRightCaption = document.createElement('button');
			paddingRightCaption.classList.add(this.CSS.button, 'disabled');
			// paddingRightCaption.appendChild($.svg('arrow-right', 10, 10));
			paddingRightCaption.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 380 17 10" style="enable-background:new -674 380 17 10;" xml:space="preserve"><polygon points="-671,385.7 -662.2,385.7 -664.2,387.7 -662.9,388.9 -659,384.9 -663,380.7 -664.2,381.9 -662.2,384.1 -671,384.1 	"/></svg>`;

			let paddingTopCaption = document.createElement('button');
			paddingTopCaption.classList.add(this.CSS.button, 'disabled');
			// paddingTopCaption.appendChild($.svg('arrow-up', 10, 10));
			paddingTopCaption.innerHTML = `<svg version="1.1" height="13" x="0px" y="0px" viewBox="-674 378.5 17 13" style="enable-background:new -674 378.5 17 13;" xml:space="preserve"><polygon points="-664.6,391 -664.6,382.2 -662.6,384.2 -661.4,382.9 -665.4,379 -669.6,383 -668.4,384.2 -666.2,382.2 -666.2,391 	"/></svg>`;

			let paddingBottomCaption = document.createElement('button');
			paddingBottomCaption.classList.add(this.CSS.button, 'disabled');
			// paddingBottomCaption.appendChild($.svg('arrow-down', 10, 10));
			paddingBottomCaption.innerHTML = `<svg version="1.1" height="13" x="0px" y="0px" viewBox="-674 378.5 17 13" style="enable-background:new -674 378.5 17 13;" xml:space="preserve"><polygon points="-666.2,379 -666.2,387.8 -668.4,385.8 -669.6,387 -665.4,391 -661.4,387.1 -662.6,385.8 -664.6,387.8 -664.6,379 	"/></svg>`;

			let increasePaddingLeft = document.createElement('button');
			increasePaddingLeft.classList.add(this.CSS.button);

			let decreasePaddingLeft = document.createElement('button');
			decreasePaddingLeft.classList.add(this.CSS.button);

			let increasePaddingRight = document.createElement('button');
			increasePaddingRight.classList.add(this.CSS.button);

			let decreasePaddingRight = document.createElement('button');
			decreasePaddingRight.classList.add(this.CSS.button);

			let increasePaddingTop = document.createElement('button');
			increasePaddingTop.classList.add(this.CSS.button);

			let decreasePaddingTop = document.createElement('button');
			decreasePaddingTop.classList.add(this.CSS.button);

			let increasePaddingBottom = document.createElement('button');
			increasePaddingBottom.classList.add(this.CSS.button);

			let decreasePaddingBottom = document.createElement('button');
			decreasePaddingBottom.classList.add(this.CSS.button);

			this.sidebar = sidebarWrapper;

			// Left Padding
			sidebarWrapper.appendChild(paddingLeftCaption);

			// increasePaddingLeft.appendChild($.svg('plus', 15, 15));
			increasePaddingLeft.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 381.5 17 7" style="enable-background:new -674 381.5 17 7;" xml:space="preserve"><polygon points="-664.7,388.5 -664.7,381.5 -666.3,381.5 -666.3,388.5 "/><polygon points="-669,385.8 -662,385.8 -662,384.2 -669,384.2 "/></svg>`;

			this.api.listeners.on(
				increasePaddingLeft,
				'click',
				(event) => me.increasePaddingLeft(event, increasePaddingLeft),
				false
			);
			sidebarWrapper.appendChild(increasePaddingLeft);

			// decreasePaddingLeft.appendChild($.svg('minus', 15, 15));
			decreasePaddingLeft.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 381.5 17 7" style="enable-background:new -674 381.5 17 7;" xml:space="preserve"><polygon points="-669,385.8 -662,385.8 -662,384.2 -669,384.2 "/></svg>`;

			this.api.listeners.on(
				decreasePaddingLeft,
				'click',
				(event) => me.decreasePaddingLeft(event, decreasePaddingLeft),
				false
			);
			sidebarWrapper.appendChild(decreasePaddingLeft);

			// Right Padding
			sidebarWrapper.appendChild(paddingRightCaption);
			// increasePaddingRight.appendChild($.svg('plus', 15, 15));
			increasePaddingRight.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 381.5 17 7" style="enable-background:new -674 381.5 17 7;" xml:space="preserve"><polygon points="-664.7,388.5 -664.7,381.5 -666.3,381.5 -666.3,388.5 "/><polygon points="-669,385.8 -662,385.8 -662,384.2 -669,384.2 "/></svg>`;

			this.api.listeners.on(
				increasePaddingRight,
				'click',
				(event) => me.increasePaddingRight(event, increasePaddingRight),
				false
			);
			sidebarWrapper.appendChild(increasePaddingRight);

			// decreasePaddingRight.appendChild($.svg('minus', 15, 15));
			decreasePaddingRight.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 381.5 17 7" style="enable-background:new -674 381.5 17 7;" xml:space="preserve"><polygon points="-669,385.8 -662,385.8 -662,384.2 -669,384.2 "/></svg>`;

			this.api.listeners.on(
				decreasePaddingRight,
				'click',
				(event) => me.decreasePaddingRight(event, decreasePaddingRight),
				false
			);
			sidebarWrapper.appendChild(decreasePaddingRight);

			// Top Padding
			sidebarWrapper.appendChild(paddingTopCaption);
			// increasePaddingTop.appendChild($.svg('plus', 15, 15));
			increasePaddingTop.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 381.5 17 7" style="enable-background:new -674 381.5 17 7;" xml:space="preserve"><polygon points="-664.7,388.5 -664.7,381.5 -666.3,381.5 -666.3,388.5 "/><polygon points="-669,385.8 -662,385.8 -662,384.2 -669,384.2 "/></svg>`;

			this.api.listeners.on(
				increasePaddingTop,
				'click',
				(event) => me.increasePaddingTop(event, increasePaddingTop),
				false
			);
			sidebarWrapper.appendChild(increasePaddingTop);

			// decreasePaddingTop.appendChild($.svg('minus', 15, 15));
			decreasePaddingTop.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 381.5 17 7" style="enable-background:new -674 381.5 17 7;" xml:space="preserve"><polygon points="-669,385.8 -662,385.8 -662,384.2 -669,384.2 "/></svg>`;

			this.api.listeners.on(
				decreasePaddingTop,
				'click',
				(event) => me.decreasePaddingTop(event, decreasePaddingTop),
				false
			);
			sidebarWrapper.appendChild(decreasePaddingTop);

			// Bottom Padding
			sidebarWrapper.appendChild(paddingBottomCaption);
			// increasePaddingBottom.appendChild($.svg('plus', 15, 15));
			increasePaddingBottom.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 381.5 17 7" style="enable-background:new -674 381.5 17 7;" xml:space="preserve"><polygon points="-664.7,388.5 -664.7,381.5 -666.3,381.5 -666.3,388.5 "/><polygon points="-669,385.8 -662,385.8 -662,384.2 -669,384.2 "/></svg>`;

			this.api.listeners.on(
				increasePaddingBottom,
				'click',
				(event) => me.increasePaddingBottom(event, increasePaddingBottom),
				false
			);
			sidebarWrapper.appendChild(increasePaddingBottom);

			// decreasePaddingBottom.appendChild($.svg('minus', 15, 15));
			decreasePaddingBottom.innerHTML = `<svg version="1.1" height="10" x="0px" y="0px" viewBox="-674 381.5 17 7" style="enable-background:new -674 381.5 17 7;" xml:space="preserve"><polygon points="-669,385.8 -662,385.8 -662,384.2 -669,384.2 "/></svg>`;

			this.api.listeners.on(
				decreasePaddingBottom,
				'click',
				(event) => me.decreasePaddingBottom(event, decreasePaddingBottom),
				false
			);
			sidebarWrapper.appendChild(decreasePaddingBottom);

			this.wrapper.appendChild(sidebarWrapper);
		}
	}

	increasePaddingLeft(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
		let className = 'pl-0';
		const paddingClass = new RegExp(/\pl-.+?\b/, 'g');
		if (currentBlockElement.className.match(paddingClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(paddingClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let padding = parseInt(parts[1]);
			if (padding <= 4) {
				currentBlockElement.classList.remove('pl-'+padding);
				padding = padding + 1;
				currentBlockElement.classList.add('pl-'+padding);
			}
		}

	}

	decreasePaddingLeft(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
		let className = 'pl-0';
		const paddingClass = new RegExp(/\pl-.+?\b/, 'g');
		if (currentBlockElement.className.match(paddingClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(paddingClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let padding = parseInt(parts[1]);
			if (padding >= 1) {
				currentBlockElement.classList.remove('pl-'+padding);
				padding = padding - 1;
				currentBlockElement.classList.add('pl-'+padding);
			}
		}
	}

	increasePaddingRight(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
		let className = 'pr-0';
		const paddingClass = new RegExp(/\pr-.+?\b/, 'g');
		if (currentBlockElement.className.match(paddingClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(paddingClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let padding = parseInt(parts[1]);
			if (padding <= 4) {
				currentBlockElement.classList.remove('pr-'+padding);
				padding = padding + 1;
				currentBlockElement.classList.add('pr-'+padding);
			}
		}
	}

	decreasePaddingRight(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
		let className = 'pr-0';
		const paddingClass = new RegExp(/\pr-.+?\b/, 'g');
		if (currentBlockElement.className.match(paddingClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(paddingClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let padding = parseInt(parts[1]);
			if (padding >= 1) {
				currentBlockElement.classList.remove('pr-'+padding);
				padding = padding - 1;
				currentBlockElement.classList.add('pr-'+padding);
			}
		}
	}

	increasePaddingTop(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
		let className = 'pt-0';
		const paddingClass = new RegExp(/\pt-.+?\b/, 'g');
		if (currentBlockElement.className.match(paddingClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(paddingClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let padding = parseInt(parts[1]);
			if (padding <= 4) {
				currentBlockElement.classList.remove('pt-'+padding);
				padding = padding + 1;
				currentBlockElement.classList.add('pt-'+padding);
			}
		}
	}

	decreasePaddingTop(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
		let className = 'pt-0';
		const paddingClass = new RegExp(/\pt-.+?\b/, 'g');
		if (currentBlockElement.className.match(paddingClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(paddingClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let padding = parseInt(parts[1]);
			if (padding >= 1) {
				currentBlockElement.classList.remove('pt-'+padding);
				padding = padding - 1;
				currentBlockElement.classList.add('pt-'+padding);
			}
		}
	}

	increasePaddingBottom(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
		let className = 'pb-0';
		const paddingClass = new RegExp(/\pb-.+?\b/, 'g');
		if (currentBlockElement.className.match(paddingClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(paddingClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let padding = parseInt(parts[1]);
			if (padding <= 4) {
				currentBlockElement.classList.remove('pb-'+padding);
				padding = padding + 1;
				currentBlockElement.classList.add('pb-'+padding);
			}
		}
	}

	decreasePaddingBottom(event, button) {
		const currentBlockIndex = this.api.blocks.getCurrentBlockIndex();

		if (currentBlockIndex < 0) {
			return;
		}

		const currentBlock = this.api.blocks.getBlockByIndex(currentBlockIndex);
		if (!currentBlock) {
			return;
		}

		const currentBlockElement = currentBlock.holder;

		// let block = this.api.blocks.getBlock(currentBlockElement);
		let className = 'pb-0';
		const paddingClass = new RegExp(/\pb-.+?\b/, 'g');
		if (currentBlockElement.className.match(paddingClass)) {
			currentBlockElement.classList.forEach( cn => {
				if (cn.match(paddingClass)) {
					className = cn;
				}
			});
			let parts = className.split('-');
			let padding = parseInt(parts[1]);
			if (padding >= 1) {
				currentBlockElement.classList.remove('pb-'+padding);
				padding = padding - 1;
				currentBlockElement.classList.add('pb-'+padding);
			}
		}
	}
}