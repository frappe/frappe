import "../dom";
frappe.provide("frappe.ui");

frappe.ui.menu = class ContextMenu {
	constructor(opts) {
		this.template = $(`<div class="sidebar-header-menu context-menu" role="menu"></div>`);
		this.menu_items = opts.menu_items;
		this.name = frappe.utils.get_random(5);
		this.open_on_left = opts.open_on_left;
		this.size = opts.size;
		this.opts = opts;
	}

	make() {
		this.template.empty();

		this.menu_items.forEach((f) => {
			f.condition =
				f.condition ||
				function () {
					return true;
				};
			if (f.condition()) {
				this.add_menu_item(f);
			}
		});

		// if (!$.contains(document.body, this.template[0])) {
		// 	$(document.body).append(this.template);
		// }
		$(document.body).append(this.template);
		this.set_styles();
	}
	set_styles() {
		if (this.size) {
			this.template.css({
				width: this.size,
			});
		}
	}
	add_menu_item(item) {
		const me = this;
		let item_wrapper = $(
			`<div class="dropdown-menu-item"><div class="dropdown-divider documentation-links"></div></div>`
		);
		if (item?.is_divider) {
			item_wrapper = $(
				`<div class="dropdown-menu-item"><div class="dropdown-divider documentation-links"></div></div>`
			);
		} else {
			item_wrapper = $(`<div class="dropdown-menu-item">
				<a>
					<div class="menu-item-icon" ${!(item.icon || item.icon_url) ? "hidden" : ""}>
						${
							item.icon
								? frappe.utils.icon(item.icon)
								: `<img
								class="logo"
								src="${item.icon_url}"
							>`
						}
					</div>
					<span class="menu-item-title">${__(item.label)}</span>
					<div class="menu-item-icon" style="margin-left:auto">
						${item.items && item.items.length ? frappe.utils.icon("chevron-right") : ""}
					</div>

				</a>
			</div>`);
			if (!item.url) {
				item_wrapper.on("click", function () {
					item.onClick && item.onClick();
					if (!(item.items && item.items.length)) {
						me.opts.onItemClick && me.opts.onItemClick(me.opts.parent);
						me.hide();
					}
				});
			} else if (item.items) {
				$();
			} else {
				$(item_wrapper).find("a").attr("href", item.url);
			}
		}
		item_wrapper.appendTo(this.template);
		if (item.items) {
			this.handle_nested_menu(item_wrapper, item);
		}
	}
	handle_nested_menu(item_wrapper, item) {
		frappe.ui.create_menu({
			parent: item_wrapper,
			menu_items: item.items,
			nested: true,
			parent_menu: this.name,
		});
	}
	show(parent) {
		// this.close_all_other_menu();

		this.make();

		const offset = $(parent).offset();
		const height = $(parent).outerHeight();
		this.left_offset = 0;
		this.gap = 4;
		if (this.opts.nested && this.opts.parent_menu) {
			let top =
				parent.getBoundingClientRect().bottom - parent.getBoundingClientRect().height;
			let dropdown = frappe.menu_map[this.opts.parent_menu].template;
			let width = dropdown.outerWidth();
			let offset = $(dropdown).offset();
			this.template.css({
				display: "block",
				position: "absolute",
				top: top + "px",
				left: offset.left + width + this.gap + "px",
			});
		} else {
			this.template.css({
				display: "block",
				position: "absolute",
				top: offset.top + height + this.gap + "px",
				left: offset.left,
			});
		}

		if (this.open_on_left) {
			this.left_offset = parent.getBoundingClientRect().width;
			this.template.css({
				left:
					offset.left -
					this.template.get(0).getBoundingClientRect().width +
					this.left_offset +
					"px",
			});
		}

		this.visible = true;
	}
	close_all_other_menu() {
		$(".context-menu").hide();
	}
	hide() {
		this.template.css("display", "none");
		this.visible = false;
	}
	mouseX(evt) {
		if (evt.pageX) {
			return evt.pageX;
		} else if (evt.clientX) {
			return (
				evt.clientX +
				(document.documentElement.scrollLeft
					? document.documentElement.scrollLeft
					: document.body.scrollLeft)
			);
		} else {
			return null;
		}
	}

	mouseY(evt) {
		if (evt.pageY) {
			return evt.pageY;
		} else if (evt.clientY) {
			return (
				evt.clientY +
				(document.documentElement.scrollTop
					? document.documentElement.scrollTop
					: document.body.scrollTop)
			);
		} else {
			return null;
		}
	}
};

frappe.menu_map = {};

frappe.ui.create_menu = function (opts) {
	$(opts.parent).css("cursor", "pointer");
	let context_menu = new frappe.ui.menu(opts);

	frappe.menu_map[context_menu.name] = context_menu;
	if (opts.right_click) {
		$(opts.parent).on("contextmenu", function (event) {
			event.preventDefault();
			event.stopPropagation();
			if (frappe.menu_map[context_menu.name] && frappe.menu_map[context_menu.name].visible) {
				frappe.menu_map[context_menu.name].hide();
				opts.onHide && opts.onHide(this);
			} else {
				frappe.menu_map[context_menu.name].show(this);
				opts.onShow && opts.onShow(this);
			}
		});
	} else {
		$(opts.parent).on("click", function (event) {
			event.preventDefault();
			event.stopPropagation();
			if (frappe.menu_map[context_menu.name].visible) {
				frappe.menu_map[context_menu.name].hide();
				opts.onHide && opts.onHide(this);
			} else {
				frappe.menu_map[context_menu.name].show(this);
				opts.onShow && opts.onShow(this);
			}
		});
	}

	$(document).on("click", function () {
		if (frappe.menu_map[context_menu.name].visible) {
			frappe.menu_map[context_menu.name].hide();
			opts.onHide && opts.onHide(opts.parent);
		}
	});

	$(document).on("keydown", function (e) {
		if (e.key === "Escape" && frappe.menu_map[context_menu.name].visible) {
			frappe.menu_map[context_menu.name].hide();
			opts.onHide && opts.onHide(opts.parent);
		}
	});
};
