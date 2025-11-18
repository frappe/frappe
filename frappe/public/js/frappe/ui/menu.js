import "../dom";
frappe.provide("frappe.ui");

frappe.ui.menu = class ContextMenu {
	constructor(menu_items, left) {
		this.template = $(`<div class="dropdown-menu context-menu" role="menu"></div>`);
		this.menu_items = menu_items;
		this.open_on_left = left;
	}

	make() {
		this.template.empty();

		this.menu_items.forEach((f) => {
			this.add_menu_item(f);
		});

		if (!$.contains(document.body, this.template[0])) {
			$(document.body).append(this.template);
		}
	}
	add_menu_item(item) {
		const me = this;
		let item_wrapper = $(`<div class="dropdown-menu-item">
			<a>
				<div class="sidebar-item-icon">
					${
						item.icon
							? frappe.utils.icon(item.icon)
							: `<img
							class="logo"
							src="${item.icon_url}"
						>`
					}
				</div>
				<span class="menu-item-title">${item.label}</span>
			</a>
		</div>`);
		if (!item.url) {
			item_wrapper.on("click", function () {
				item.onClick();
				me.hide();
			});
		} else {
			$(item_wrapper).find("a").attr("href", item.url);
		}
		item_wrapper.appendTo(this.template);
	}
	show(element) {
		this.close_all_other_menu();

		this.make();

		const offset = $(element).offset();
		const height = $(element).outerHeight();
		this.left_offset = 0;

		this.template.css({
			display: "block",
			position: "absolute",
			top: offset.top + height + "px",
			left: offset.left,
		});
		if (this.open_on_left) {
			this.left_offset = element.getBoundingClientRect().width;
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

frappe.ui.create_menu = function attachContextMenuToElement(
	element,
	menuItems,
	right_click,
	open_on_left
) {
	let contextMenu = new frappe.ui.menu(menuItems, open_on_left);

	frappe.menu_map[$(element).data("menu")] = contextMenu;
	if (right_click) {
		$(element).on("contextmenu", function (event) {
			event.preventDefault();
			event.stopPropagation();
			if (
				frappe.menu_map[$(element).data("menu")] &&
				frappe.menu_map[$(element).data("menu")].visible
			) {
				frappe.menu_map[$(element).data("menu")].hide();
			} else {
				frappe.menu_map[$(element).data("menu")].show(this);
			}
		});
	} else {
		$(element).on("click", function (event) {
			event.preventDefault();
			event.stopPropagation();
			if (frappe.menu_map[$(element).data("menu")].visible) {
				frappe.menu_map[$(element).data("menu")].hide();
			} else {
				frappe.menu_map[$(element).data("menu")].show(this);
			}
		});
	}

	$(document).on("click", function () {
		if (frappe.menu_map[$(element).data("menu")].visible) {
			frappe.menu_map[$(element).data("menu")].hide();
		}
	});

	$(document).on("keydown", function (e) {
		if (e.key === "Escape" && frappe.menu_map[$(element).data("menu")].visible) {
			frappe.menu_map[$(element).data("menu")].hide();
		}
	});
};
