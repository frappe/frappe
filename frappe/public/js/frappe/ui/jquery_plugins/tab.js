import { after_transition, call_method, get_target, reflow, trigger } from "./utils";

const DATA_KEY = "bs.tab";
const EVENT_KEY = ".bs.tab";
const TOGGLE = '[data-toggle="tab"], [data-toggle="pill"], [data-toggle="list"]';

const is_list = (element) => element && ["UL", "OL"].includes(element.nodeName);
const active_in = (container) =>
	is_list(container) ? $(container).find("> li > .active") : $(container).children(".active");

class Tab {
	constructor(element) {
		this.element = element;
	}

	show() {
		const element = this.element;
		if (
			(element.parentNode?.nodeType === Node.ELEMENT_NODE &&
				element.classList.contains("active")) ||
			element.classList.contains("disabled") ||
			element.hasAttribute("disabled")
		) {
			return;
		}

		const list = $(element).closest(".nav, .list-group")[0];
		let previous;
		if (list) {
			const items = $(list).find(is_list(list) ? "> li > .active" : ".active");
			previous = items[items.length - 1];
		}

		const hide_event = $.Event(`hide${EVENT_KEY}`, { relatedTarget: element });
		const show_event = $.Event(`show${EVENT_KEY}`, { relatedTarget: previous });
		if (previous) $(previous).trigger(hide_event);
		$(element).trigger(show_event);
		if (show_event.isDefaultPrevented() || hide_event.isDefaultPrevented()) return;

		const target = get_target(element);
		this.activate(element, list);

		const complete = () => {
			trigger(previous, `hidden${EVENT_KEY}`, { relatedTarget: element });
			trigger(element, `shown${EVENT_KEY}`, { relatedTarget: previous });
		};
		if (target) this.activate(target, target.parentNode, complete);
		else complete();
	}

	dispose() {
		$.removeData(this.element, DATA_KEY);
		this.element = null;
	}

	activate(element, container, callback) {
		const active = active_in(container)[0];
		const done = () => this.mark_active(element, active, callback);
		if (callback && active?.classList.contains("fade")) {
			active.classList.remove("show");
			after_transition(active, done);
		} else {
			done();
		}
	}

	mark_active(element, active, callback) {
		if (active) {
			active.classList.remove("active");
			$(active.parentNode).find("> .dropdown-menu .active").removeClass("active");
			if (active.getAttribute("role") === "tab") active.setAttribute("aria-selected", false);
		}

		element.classList.add("active");
		if (element.getAttribute("role") === "tab") element.setAttribute("aria-selected", true);
		reflow(element);
		if (element.classList.contains("fade")) element.classList.add("show");

		let parent = element.parentNode;
		if (parent?.nodeName === "LI") parent = parent.parentNode;
		if (parent?.classList?.contains("dropdown-menu")) {
			const dropdown = $(element).closest(".dropdown")[0];
			if (dropdown) $(dropdown.querySelectorAll(".dropdown-toggle")).addClass("active");
			element.setAttribute("aria-expanded", true);
		}

		callback?.();
	}
}

$(document).on(`click${EVENT_KEY}.data-api`, TOGGLE, function (e) {
	e.preventDefault();
	$.fn.tab.call($(this), "show");
});

$.fn.tab = function (config) {
	return this.each(function () {
		let tab = $(this).data(DATA_KEY);
		if (!tab) {
			tab = new Tab(this);
			$(this).data(DATA_KEY, tab);
		}
		if (typeof config === "string") call_method(tab, config);
	});
};
$.fn.tab.Constructor = Tab;
