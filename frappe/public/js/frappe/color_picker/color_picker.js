import utils from './utils';

class Picker {
	constructor(opts) {
		this.parent = opts.parent;
		this.width = opts.width;
		this.height = opts.height;
		this.set_color(opts.color);
		this.swatches = opts.swatches;
		this.setup_picker();
	}

	refresh() {
		this.set_selector_position(true);
		this.update_color_map();
	}

	setup_picker() {
		let color_picker_template = document.createElement('template');
		color_picker_template.innerHTML = `
			<div class="color-picker">
				<div class="swatch-section">
					${__('SWATCHES')}<br>
					<div class="swatches"></div>
				</div>
				${__('COLOR PICKER')}<br>
				<div class="color-map">
					<div class="color-selector"></div>
				</div>
				<div class="hue-map">
					<div class="hue-selector"></div>
				</div>
			</div>
		`.trim();
		this.color_picker_wrapper = color_picker_template.content.firstElementChild.cloneNode(true);
		this.parent.appendChild(this.color_picker_wrapper);
		this.color_map = this.color_picker_wrapper.getElementsByClassName('color-map')[0];
		this.color_selector_circle = this.color_map.getElementsByClassName('color-selector')[0];
		this.hue_map = this.color_picker_wrapper.getElementsByClassName('hue-map')[0];
		this.swatches_wrapper = this.color_picker_wrapper.getElementsByClassName('swatches')[0];
		this.hue_selector_circle = this.hue_map.getElementsByClassName('hue-selector')[0];
		this.refresh();
		this.setup_events();
		this.setup_swatches();
	}

	setup_events() {
		this.setup_hue_event();
		this.setup_color_event();
	}

	setup_swatches() {
		let swatch_template = document.createElement('template');
		swatch_template.innerHTML = '<div class="swatch" tabindex=0></div>';
		this.swatches.forEach(color => {
			let swatch = swatch_template.content.firstElementChild.cloneNode(true);
			this.swatches_wrapper.appendChild(swatch);
			const set_values = () => {
				this.set_color(color);
				this.set_selector_position();
				this.update_color_map();
			};
			swatch.addEventListener('click', () => {
				set_values();
			});
			swatch.onkeydown = (e) => {
				const key_code = e.keyCode;
				if ([13, 32].includes(key_code)) {
					e.preventDefault();
					set_values();
				}
			};
			swatch.style.backgroundColor = color;
		});
	}

	set_selector_position(silent) {
		this.hue = utils.get_hue(this.get_color());
		this.color_selector_position = this.get_pointer_coords();
		this.hue_selector_position = {
			x: this.hue * this.hue_map.offsetWidth / 360,
			y: this.hue_map.offsetHeight / 2
		};
		this.update_color_selector(silent);
		this.update_hue_selector(silent);
	}

	setup_color_event() {
		let on_drag = (x, y) => {
			this.color_selector_position.x = x;
			this.color_selector_position.y = y;
			this.update_color();
			this.update_color_selector();
		};
		this.setup_drag_event(this.color_map, on_drag);
	}

	update_color() {
		let x = this.color_selector_position.x;
		let y = this.color_selector_position.y;
		let w = this.color_map.offsetWidth;
		let h = this.color_map.offsetHeight;
		let color = utils.hsv_to_hex(
			this.hue,
			Math.round(x / w * 100),
			Math.round((1 - (y / h)) * 100),
		);
		this.set_color(color);
	}

	update_color_selector(silent) {
		let x = this.color_selector_position.x;
		let y = this.color_selector_position.y;
		// set color selector position and background
		this.color_selector_circle.style.top = (y - this.color_selector_circle.offsetHeight / 2) + 'px';
		this.color_selector_circle.style.left = (x - this.color_selector_circle.offsetWidth / 2) + 'px';
		this.color_map.style.color = this.get_color();
		!silent && this.on_change && this.on_change(this.get_color());
	}

	setup_hue_event() {
		// eslint-disable-next-line no-unused-vars
		let on_drag = (x, y) => {
			this.hue_selector_position.x = x;
			this.hue = Math.round(x * 360 / this.hue_map.offsetWidth);
			this.update_color_map();
			this.update_hue_selector();
			this.update_color();
			this.update_color_selector();
		};
		this.setup_drag_event(this.hue_map, on_drag);
	}

	update_color_map() {
		this.color_map.style.background = `
			linear-gradient(0deg, black, transparent),
			linear-gradient(90deg, white, transparent),
			hsl(${this.hue}, 100%, 50%)
		`;
	}

	update_hue_selector() {
		let x = this.hue_selector_position.x - 1;
		let y = (this.hue_map.offsetHeight / 2) - 1;
		// set color selector position and background
		this.hue_selector_circle.style.top = (y - this.hue_selector_circle.offsetHeight / 2) + 'px';
		this.hue_selector_circle.style.left = (x - this.hue_selector_circle.offsetWidth / 2) + 'px';
		this.hue_map.style.color = `hsl(${this.hue}, 100%, 50%)`;
	}

	get_pointer_coords() {
		// eslint-disable-next-line no-unused-vars
		let h, s, v;
		// eslint-disable-next-line no-unused-vars
		[h, s, v] = utils.get_hsv(this.get_color());
		let width = this.color_map.offsetWidth;
		let height = this.color_map.offsetHeight;
		let x = utils.clamp(0, s * width / 100, width);
		let y = utils.clamp(0, (1 - (v / 100)) * height, height);
		return {x, y};
	}

	setup_drag_event(element, callback) {
		let on_drag = (event, force) => {
			if (element.drag_enabled || force) {
				event.preventDefault();
				event = event.touches ? event.touches[0] : event;
				let element_bounds = element.getBoundingClientRect();
				let x = event.clientX - element_bounds.left;
				let y = event.clientY - element_bounds.top;
				x = utils.clamp(0, x, element_bounds.width);
				y = utils.clamp(0, y, element_bounds.height);
				callback(x, y);
			}
		};

		element.addEventListener("mousedown", () => element.drag_enabled = true);
		document.addEventListener("mouseup", () => element.drag_enabled = false);
		document.addEventListener("mousemove", on_drag);
		element.addEventListener("click", (event) => on_drag(event, true));

		element.addEventListener("touchstart", () => element.drag_enabled = true);
		element.addEventListener("touchend", () => element.drag_enabled = false);
		element.addEventListener("touchcancel", () => element.drag_enabled = false);
		element.addEventListener("touchmove", (event) => {
			if (event.touches.length == 1) {
				on_drag(event);
			} else {
				element.drag_enabled = false;
			}
		});
	}

	set_color(color) {
		this.color = color || '#ffffff';
	}

	get_color() {
		return this.color || '#ffffff';
	}
}

export default Picker;