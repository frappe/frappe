class Picker {
	constructor(opts) {
		this.parent = opts.parent;
		this.width = opts.width;
		this.height = opts.height;
		this.set_icon(opts.icon);
		this.icons = opts.icons;
		this.include_emoji = opts.include_emoji;
		this.setup_picker();
	}

	refresh() {
		this.update_icon_selected(true);
	}

	setup_picker() {
		this.icon_picker_wrapper = $(`
			<div class="icon-picker">
				<div class="search-icons">
					<input type="search" placeholder="${__("Search for icons...")}" class="form-control">
					<span class="search-icon">${frappe.utils.icon("search", "sm")}</span>
				</div>
				<div class="icon-section" id='icon-section'>
					<div class="icons"></div>
				</div>
			</div>
		`);
		this.parent.append(this.icon_picker_wrapper);
		this.icon_wrapper = this.icon_picker_wrapper.find(".icons");
		this.search_input = this.icon_picker_wrapper.find(".search-icons > input");
		this.refresh();
		this.setup_icons();
		if (this.include_emoji) {
			this.setup_emojis();
		}
	}
	setup_emojis() {
		this.setup_tab();
		this.setup_emoji_container();
		this.emoji_wrapper = this.icon_picker_wrapper.find(".emojis");
		frappe.utils.get_emojis().forEach((emoji) => {
			const $icon = $(`<div id="${emoji}" class="emoji-wrapper">${emoji}</div>`);
			this.emoji_wrapper.append($icon);
			$icon.on("click", () => {
				this.set_icon(emoji);
				this.update_icon_selected();
			});
		});
	}
	filter_emojis() {
		this.emoji_wrapper.find(".emoji-wrapper").removeClass("hidden");
	}
	setup_emoji_container() {
		this.icon_picker_wrapper.find(".icon-section")
			.after(`<div class="emoji-section hidden" id='emoji-section'>
			<div class="emojis"></div>
			</div>`);
	}
	setup_tab() {
		this.icon_picker_wrapper.find(".search-icons").after(`<div class="form-tabs-list">
				<ul class="nav form-tabs" id="form-tabs" role="tablist">
					<li class="nav-item show">
						<button class="nav-link active" data-toggle="tab" role="tab" aria-selected="true">
								Icon
						</button>
					</li>
					<li class="nav-item show">
						<button class="nav-link" data-toggle="tab" role="tab" aria-selected="true">
								Emoji
						</button>
					</li>
				</ul>
			</div>`);
		let icon_types = ["icon", "emoji"];
		const me = this;

		this.icon_picker_wrapper.find(".nav-item").on("click", function (e) {
			let container_name = $(this).text().trim().toLowerCase();

			icon_types.forEach((type) => {
				if (type === container_name) {
					me.icon_picker_wrapper.find(`.${type}-section`).removeClass("hidden");
				} else {
					me.icon_picker_wrapper.find(`.${type}-section`).addClass("hidden");
				}
			});
		});
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
