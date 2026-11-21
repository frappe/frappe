import { Anchor } from "./anchor";
import {
	call_method,
	get_selector,
	is_element,
	is_touch_device,
	to_element,
	trigger,
} from "./utils";

const DATA_KEY = "bs.dropdown";
const EVENT_KEY = ".bs.dropdown";
const DATA_API = `${EVENT_KEY}.data-api`;
const KEY = { ESCAPE: 27, SPACE: 32, TAB: 9, UP: 38, DOWN: 40 };
const RIGHT_MOUSE_BUTTON = 3;
const TOGGLE = '[data-toggle="dropdown"]';
const MENU = ".dropdown-menu";
const VISIBLE_ITEMS = ".dropdown-menu .dropdown-item:not(.disabled):not(:disabled)";
const DEFAULTS = {
	offset: 0,
	flip: true,
	boundary: "scrollParent",
	reference: "toggle",
	display: "dynamic",
};

const parent_of = (toggle) => {
	const selector = get_selector(toggle);
	return (selector && document.querySelector(selector)) || toggle.parentNode;
};
const is_disabled = (toggle) => toggle.disabled || toggle.classList.contains("disabled");

class Dropdown {
	constructor(element, config) {
		this.element = element;
		this.anchor = null;
		this.config = { ...DEFAULTS, ...$(element).data(), ...config };
		this.menu = parent_of(element)?.querySelector(MENU) || null;
		this.in_navbar = $(element).closest(".navbar").length > 0;

		$(element).on(`click${EVENT_KEY}`, (e) => {
			e.preventDefault();
			e.stopPropagation();
			this.toggle();
		});
	}

	toggle() {
		if (is_disabled(this.element)) return;
		const is_open = this.menu.classList.contains("show");
		Dropdown.close_all();
		if (!is_open) this.show(true);
	}

	show(position = false) {
		if (is_disabled(this.element) || this.menu.classList.contains("show")) return;

		const related = { relatedTarget: this.element };
		const parent = parent_of(this.element);
		if (trigger(parent, `show${EVENT_KEY}`, related).isDefaultPrevented()) return;

		if (!this.in_navbar && position) {
			if (this.config.boundary !== "scrollParent") parent.classList.add("position-static");
			this.anchor = new Anchor(this.get_reference(parent), this.menu, {
				placement: this.get_placement(),
				offset: this.config.offset,
				flip: this.config.flip,
				boundary: this.config.boundary,
				apply_style: this.config.display !== "static",
			});
		}

		if (is_touch_device() && !$(parent).closest(".navbar-nav").length) {
			$(document.body).children().on("mouseover", null, $.noop);
		}

		this.element.focus();
		this.element.setAttribute("aria-expanded", true);
		$(this.menu).toggleClass("show");
		$(parent).toggleClass("show");
		trigger(parent, `shown${EVENT_KEY}`, related);
	}

	hide() {
		if (is_disabled(this.element) || !this.menu.classList.contains("show")) return;

		const related = { relatedTarget: this.element };
		const parent = parent_of(this.element);
		if (trigger(parent, `hide${EVENT_KEY}`, related).isDefaultPrevented()) return;

		this.anchor?.destroy();
		$(this.menu).toggleClass("show");
		$(parent).toggleClass("show");
		trigger(parent, `hidden${EVENT_KEY}`, related);
	}

	dispose() {
		$.removeData(this.element, DATA_KEY);
		$(this.element).off(EVENT_KEY);
		this.anchor?.destroy();
		this.element = this.menu = this.anchor = null;
	}

	update() {
		this.in_navbar = $(this.element).closest(".navbar").length > 0;
		this.anchor?.schedule_update();
	}

	get_reference(parent) {
		if (this.config.reference === "parent") return parent;
		if (is_element(this.config.reference)) return to_element(this.config.reference);
		return this.element;
	}

	get_placement() {
		const wrapper = this.element.parentNode.classList;
		const menu_right = this.menu.classList.contains("dropdown-menu-right");
		if (wrapper.contains("dropup")) return menu_right ? "top-end" : "top-start";
		if (wrapper.contains("dropright")) return "right-start";
		if (wrapper.contains("dropleft")) return "left-start";
		return menu_right ? "bottom-end" : "bottom-start";
	}

	static close_all(event) {
		if (
			event &&
			(event.which === RIGHT_MOUSE_BUTTON ||
				(event.type === "keyup" && event.which !== KEY.TAB))
		) {
			return;
		}

		for (const toggle of document.querySelectorAll(TOGGLE)) {
			const parent = parent_of(toggle);
			const dropdown = $(toggle).data(DATA_KEY);
			if (!dropdown || !parent.classList.contains("show")) continue;

			const keeps_open =
				event &&
				((event.type === "click" && /input|textarea/i.test(event.target.tagName)) ||
					(event.type === "keyup" && event.which === KEY.TAB)) &&
				$.contains(parent, event.target);
			if (keeps_open) continue;

			const related = { relatedTarget: toggle };
			if (event?.type === "click") related.clickEvent = event;
			if (trigger(parent, `hide${EVENT_KEY}`, related).isDefaultPrevented()) continue;

			if (is_touch_device()) $(document.body).children().off("mouseover", null, $.noop);
			toggle.setAttribute("aria-expanded", "false");
			dropdown.anchor?.destroy();
			dropdown.menu.classList.remove("show");
			parent.classList.remove("show");
			trigger(parent, `hidden${EVENT_KEY}`, related);
		}
	}

	static handle_keydown(event) {
		const key = event.which;
		const in_field = /input|textarea/i.test(event.target.tagName);
		const is_command = in_field
			? key !== KEY.SPACE &&
			  (key === KEY.ESCAPE ||
					((key === KEY.DOWN || key === KEY.UP) &&
						!$(event.target).closest(MENU).length))
			: [KEY.UP, KEY.DOWN, KEY.ESCAPE].includes(key);
		if (!is_command || is_disabled(this)) return;

		const parent = parent_of(this);
		const is_open = parent.classList.contains("show");
		if (!is_open && key === KEY.ESCAPE) return;

		event.preventDefault();
		event.stopPropagation();

		if (!is_open || key === KEY.ESCAPE || key === KEY.SPACE) {
			if (key === KEY.ESCAPE) $(parent.querySelector(TOGGLE)).trigger("focus");
			$(this).trigger("click");
			return;
		}

		const items = [...parent.querySelectorAll(VISIBLE_ITEMS)].filter((item) =>
			$(item).is(":visible")
		);
		if (!items.length) return;

		let index = items.indexOf(event.target);
		if (key === KEY.UP && index > 0) index--;
		if (key === KEY.DOWN && index < items.length - 1) index++;
		items[Math.max(index, 0)].focus();
	}
}

$(document)
	.on(`keydown${DATA_API}`, TOGGLE, Dropdown.handle_keydown)
	.on(`keydown${DATA_API}`, MENU, Dropdown.handle_keydown)
	.on(`click${DATA_API} keyup${DATA_API}`, Dropdown.close_all)
	.on(`click${DATA_API}`, TOGGLE, function (e) {
		e.preventDefault();
		e.stopPropagation();
		$.fn.dropdown.call($(this), "toggle");
	})
	.on(`click${DATA_API}`, ".dropdown form", (e) => e.stopPropagation());

$.fn.dropdown = function (config) {
	return this.each(function () {
		let dropdown = $(this).data(DATA_KEY);
		if (!dropdown) {
			dropdown = new Dropdown(this, typeof config === "object" ? config : null);
			$(this).data(DATA_KEY, dropdown);
		}
		if (typeof config === "string") call_method(dropdown, config);
	});
};
$.fn.dropdown.Constructor = Dropdown;
