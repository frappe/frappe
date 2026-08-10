class Picker {
	constructor(opts) {
		this.parent = opts.parent;
		this.width = opts.width;
		this.height = opts.height;
		this.set_icon(opts.icon);
		// [{ label, icons }] -- a section renders a heading only when it is labelled
		this.sections = opts.sections;
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
				<div class="icon-section" id='icon-section'></div>
			</div>
		`);
		this.parent.append(this.icon_picker_wrapper);
		this.icon_section = this.icon_picker_wrapper.find(".icon-section");
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
		this.sections.forEach((section) => {
			this.setup_section(section);
		});
		this.search_input.keyup((e) => {
			e.preventDefault();
			this.filter_icons();
		});

		this.search_input.on("search", () => {
			this.filter_icons();
		});
	}

	setup_section({ label, icons }) {
		let $group = $(`<div class="icon-group">
				${label ? `<div class="icon-group-label">${label}</div>` : ""}
				<div class="icons"></div>
			</div>`);
		this.icon_section.append($group);

		let $icons = $group.find(".icons");
		icons.forEach((icon) => {
			let $icon = $(
				`<div id="${icon}" class="icon-wrapper">${frappe.utils.icon(icon, "md")}</div>`
			);
			$icons.append($icon);
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
	}

	filter_icons() {
		let value = this.search_input.val();
		let $icons = this.icon_section.find(".icon-wrapper");
		if (!value) {
			$icons.removeClass("hidden");
		} else {
			$icons.addClass("hidden");
			this.icon_section.find(`.icon-wrapper[id*='${value}']`).removeClass("hidden");
		}
		// a labelled section with nothing left to show would sit above an empty grid
		this.icon_section.find(".icon-group").each(function () {
			$(this).toggleClass("hidden", !$(this).find(".icon-wrapper:not(.hidden)").length);
		});
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
