class Picker {
	constructor(opts) {
		this.parent = opts.parent;
		this.width = opts.width;
		this.height = opts.height;
		this.set_icon(opts.icon);
		this.icons = opts.icons;
		this.setup_picker();
	}

	refresh() {
		this.update_icon_selected(true);
	}

	setup_picker() {
		this.icon_picker_wrapper = $(`
			<div class="icon-picker">
				<div class="search-icons">
					<input type="search" placeholder="Search for icons.." class="form-control">
					<span class="search-icon">${frappe.utils.icon("search", "sm")}</span>
				</div>
				<div class="icon-section">
					<div class="icons"></div>
				</div>
			</div>
		`);
		this.parent.append(this.icon_picker_wrapper);
		this.icon_wrapper = this.icon_picker_wrapper.find(".icons");
		this.search_input = this.icon_picker_wrapper.find(".search-icons > input");
		this.refresh();
		this.setup_icons();
	}

	setup_icons() {
		this.icons.forEach((icon) => {
			let $icon = $(
				`<div id="${icon}" class="icon-wrapper">${frappe.utils.icon(icon, "md")}</div>`
			);
			this.icon_wrapper.append($icon);
			const set_values = () => {
				this.set_icon(icon);
				this.update_icon_selected();
			};
			$icon.on("click", () => {
				set_values();
			});
			$icon.keydown((e) => {
				const key_code = e.keyCode;
				if ([13, 32].includes(key_code)) {
					e.preventDefault();
					set_values();
				}
			});
		});
		this.search_input.keyup((e) => {
			e.preventDefault();
			this.filter_icons();
		});

		this.search_input.on("search", () => {
			this.filter_icons();
		});
	}

	filter_icons() {
		let value = this.search_input.val();
		if (!value) {
			this.icon_wrapper.find(".icon-wrapper").removeClass("hidden");
		} else {
			this.icon_wrapper.find(".icon-wrapper").addClass("hidden");
			this.icon_wrapper.find(`.icon-wrapper[id*='${value}']`).removeClass("hidden");
		}
	}

	update_icon_selected(silent) {
		!silent && this.on_change && this.on_change(this.get_icon());
	}

	set_icon(icon) {
		this.icon = icon || "";
	}

	get_icon() {
		return this.icon || "";
	}
}

export default Picker;
