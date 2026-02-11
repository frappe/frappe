import "../dom";
frappe.provide("frappe.ui");

frappe.ui.menu = class ContextMenu {
	constructor(opts) {
		this.template = $(`<div class="frappe-menu context-menu" role="menu"></div>`);
		this.menu_items = opts.menu_items;
		this.name = frappe.utils.get_random(5);
		this.open_on_left = opts.open_on_left;
		this.size = opts.size;
		this.opts = opts;
		Object.assign(this, opts);
		this.nested_menus = [];
		this.setup_menu_toggle();
	}
	setup_menu_toggle() {
		const me = this;
		if (this.opts.right_click) {
			$(this.opts.parent).on("contextmenu", function (event) {
				event.preventDefault();
				event.stopPropagation();
				if (me.visible) {
					me.hide();
					me.opts.onHide && me.opts.onHide(me.parent);
				} else {
					me.show(event);
					me.opts.onShow && me.opts.onShow(me.parent);
				}
			});
		} else {
			$(this.opts.parent).on("click", function (event) {
				event.preventDefault();
				event.stopPropagation();
				if (!me.parent_menu) {
					if (me.visible) {
						me.hide();
						me.opts.onHide && me.opts.onHide(me.parent);
					} else {
						me.show(event);
						me.opts.onShow && me.opts.onShow(me.parent);
					}
				}
			});
		}
	}
	make() {
		this.template.empty();
		this.menu_items_to_show = [];
		this.menu_items.forEach((f) => {
			f.condition =
				f.condition ||
				function () {
					return true;
				};
			if (f.condition()) {
				this.add_menu_item(f);
				this.menu_items_to_show.push(f);
			}
		});

		// if (!$.contains(document.body, this.template[0])) {
		// 	$(document.body).append(this.template);
		// }

		// only append if there are items to show
		if (this.menu_items_to_show.length > 0) {
			$(document.body).append(this.template);
		}

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
		item.nested_menus = [];
		let item_wrapper = $(
			`<div class="dropdown-menu-item"><div class="dropdown-divider documentation-links"></div></div>`
		);
		if (item?.is_divider) {
			item_wrapper = $(
				`<div class="dropdown-menu-item"><div class="dropdown-divider documentation-links"></div></div>`
			);
		} else {
			const iconMarkup = item.icon_url
				? `<img class="logo" src="${item.icon_url}">`
				: item.icon_html
				? item.icon_html
				: item.icon
				? frappe.utils.icon(item.icon)
				: "";
			let chevron_direction = frappe.utils.is_rtl() ? "left " : "right";
			item_wrapper = $(`<div class="dropdown-menu-item" onclick="${
				item.action ? `return ${item.action}` : ""
			}">
				<a>
					<div class="menu-item-icon" ${!(iconMarkup != "") ? "hidden" : ""}>
						${iconMarkup}
					</div>
					<span class="menu-item-title">${__(item.label)}</span>
					${
						item.items && item.items.length
							? `<div class="menu-item-icon" style="margin-left:auto">
						${frappe.utils.icon(`chevron-${chevron_direction}`)}
					</div>`
							: ""
					}
				</a>
			</div>`);
			if (!item.url) {
				item_wrapper.on("click", function (event) {
					item.onClick && item.onClick();
					if (!(item.items && item.items.length)) {
						me.opts.onItemClick && me.opts.onItemClick(me.opts.parent);
						me.hide();
					} else {
						if (!me.current_menu) {
							me.nested_menus.forEach((menu) => {
								if (menu.parent.get(0) == this) {
									me.current_menu = menu;
								}
							});
							me.current_menu.show(event);
						} else {
							if (me.current_menu.parent.get(0) == this) {
								// this ensures toggling would work on nested item's parent
								me.current_menu.hide();
								me.current_menu = null;
							} else {
								// this ensures the other nested item would close before opening the next one
								me.current_menu.hide();
								me.nested_menus.forEach((menu) => {
									if (menu.parent.get(0) == this) {
										me.current_menu = menu;
									}
								});
								me.current_menu.show();
							}
						}
					}
				});
			} else if (item.items) {
				$();
			} else {
				item_wrapper.on("click", function () {
					me.nested_menus.forEach((menu) => {
						menu.hide();
					});
					me.hide();
					me.opts.onHide && me.opts.onHide(me);
					if (item.url.startsWith("/desk")) {
						frappe.set_route(item.url);
					} else if (item.url.startsWith("/")) {
						window.location.href = window.location.origin + item.url;
					} else {
						window.open(item.url, "_blank").focus();
					}
				});
			}
		}
		item_wrapper.appendTo(this.template);
		if (item.items) {
			let nested_menu = this.handle_nested_menu(item_wrapper, item);
			this.nested_menus.push(nested_menu);
		}
	}

	handle_nested_menu(item_wrapper, item) {
		return frappe.ui.create_menu({
			parent: item_wrapper,
			menu_items: item.items,
			nested: true,
			parent_data: item,
			parent_menu: this.name,
		});
	}

	show(event) {
		this.make();
		this.gap = 4;

		if (this.opts.right_click && event) {
			this.template.css({
				display: "block",
				position: "fixed",
				left: `${event.clientX}px`,
				top: `${event.clientY}px`,
			});
			this.visible = true;
			frappe.visible_menus.push(this);
			return;
		}

		const parent_rect = this.parent.get(0).getBoundingClientRect();
		let top, left;

		if (this.opts.nested && this.opts.parent_menu) {
			let parent_menu_el = frappe.menu_map[this.opts.parent_menu].template;
			let parent_menu_rect = parent_menu_el.get(0).getBoundingClientRect();
			top = parent_rect.top;
			if (frappe.utils.is_rtl()) {
				left = parent_menu_rect.left - this.template.outerWidth() - this.gap;
			} else {
				left = parent_menu_rect.right + this.gap;
			}
		} else {
			top = parent_rect.bottom + this.gap;
			left = parent_rect.left;
			if (this.open_on_left || frappe.utils.is_rtl()) {
				left = parent_rect.right - this.template.outerWidth();
			}
		}

		if (left < 0) left = 10;

		this.template.css({
			display: "block",
			position: "fixed",
			top: top + "px",
			left: left + "px",
		});

		this.visible = true;
		frappe.visible_menus.push(this);
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
frappe.visible_menus = [];

frappe.ui.create_menu = function (opts) {
	if (!opts.right_click) $(opts.parent).css("cursor", "pointer");
	let context_menu = new frappe.ui.menu(opts);

	frappe.menu_map[context_menu.name] = context_menu;

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
	return context_menu;
};

function close_all_open_menus() {
	frappe.visible_menus.forEach((menu) => {
		menu.hide();
	});
	frappe.visible_menus = [];
}

frappe.router.on("change", function () {
	close_all_open_menus();
});
