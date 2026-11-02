import { after_transition, call_method, get_selector, reflow, trigger } from "./utils";

const DATA_KEY = "bs.collapse";
const EVENT_KEY = ".bs.collapse";
const TOGGLE = '[data-toggle="collapse"]';

class Collapse {
	constructor(element, config) {
		this.element = element;
		this.is_transitioning = false;
		this.triggers = [
			...document.querySelectorAll(
				`${TOGGLE}[href="#${element.id}"], ${TOGGLE}[data-target="#${element.id}"]`
			),
		];
		for (const toggle of document.querySelectorAll(TOGGLE)) {
			const selector = get_selector(toggle);
			if (selector && [...document.querySelectorAll(selector)].includes(element)) {
				this.selector = selector;
				this.triggers.push(toggle);
			}
		}

		this.mark_triggers(element.classList.contains("show"), this.triggers);
		if (config.toggle) this.toggle();
	}

	get dimension() {
		return this.element.classList.contains("width") ? "width" : "height";
	}

	toggle() {
		if (this.element.classList.contains("show")) this.hide();
		else this.show();
	}

	show() {
		if (this.is_transitioning || this.element.classList.contains("show")) return;
		if (trigger(this.element, `show${EVENT_KEY}`).isDefaultPrevented()) return;

		const dimension = this.dimension;
		this.element.classList.remove("collapse");
		this.element.classList.add("collapsing");
		this.element.style[dimension] = 0;
		$(this.triggers).removeClass("collapsed").attr("aria-expanded", true);
		this.is_transitioning = true;

		after_transition(this.element, () => {
			this.element.classList.remove("collapsing");
			this.element.classList.add("collapse", "show");
			this.element.style[dimension] = "";
			this.is_transitioning = false;
			trigger(this.element, `shown${EVENT_KEY}`);
		});
		const scroll_size = dimension === "width" ? "scrollWidth" : "scrollHeight";
		this.element.style[dimension] = `${this.element[scroll_size]}px`;
	}

	hide() {
		if (this.is_transitioning || !this.element.classList.contains("show")) return;
		if (trigger(this.element, `hide${EVENT_KEY}`).isDefaultPrevented()) return;

		const dimension = this.dimension;
		this.element.style[dimension] = `${this.element.getBoundingClientRect()[dimension]}px`;
		reflow(this.element);
		this.element.classList.add("collapsing");
		this.element.classList.remove("collapse", "show");

		for (const toggle of this.triggers) {
			const selector = get_selector(toggle);
			if (selector !== null && !$(document.querySelectorAll(selector)).hasClass("show")) {
				$(toggle).addClass("collapsed").attr("aria-expanded", false);
			}
		}

		this.is_transitioning = true;
		this.element.style[dimension] = "";
		after_transition(this.element, () => {
			this.is_transitioning = false;
			this.element.classList.remove("collapsing");
			this.element.classList.add("collapse");
			trigger(this.element, `hidden${EVENT_KEY}`);
		});
	}

	dispose() {
		$.removeData(this.element, DATA_KEY);
		this.element = this.triggers = null;
	}

	mark_triggers(is_open, triggers) {
		$(triggers).toggleClass("collapsed", !is_open).attr("aria-expanded", is_open);
	}
}

$(document).on(`click${EVENT_KEY}.data-api`, TOGGLE, function (e) {
	if (e.currentTarget.tagName === "A") e.preventDefault();
	const $trigger = $(this);
	$(document.querySelectorAll(get_selector(this))).each(function () {
		$.fn.collapse.call($(this), $(this).data(DATA_KEY) ? "toggle" : $trigger.data());
	});
});

$.fn.collapse = function (config) {
	return this.each(function () {
		let collapse = $(this).data(DATA_KEY);
		const options = {
			toggle: true,
			...$(this).data(),
			...(typeof config === "object" && config ? config : {}),
		};
		if (!collapse && options.toggle && /show|hide/.test(config)) options.toggle = false;
		options.toggle = Boolean(options.toggle);
		if (!collapse) {
			collapse = new Collapse(this, options);
			$(this).data(DATA_KEY, collapse);
		}
		if (typeof config === "string") call_method(collapse, config);
	});
};
$.fn.collapse.Constructor = Collapse;
