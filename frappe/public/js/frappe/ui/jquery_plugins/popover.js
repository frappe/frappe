import { Tooltip, register } from "./tooltip";

class Popover extends Tooltip {
	static NAME = "popover";
	static DATA_KEY = "bs.popover";
	static EVENT_KEY = ".bs.popover";
	static CLASS_PREFIX = "bs-popover";
	static DEFAULTS = {
		...Tooltip.DEFAULTS,
		placement: "right",
		trigger: "click",
		content: "",
		template:
			'<div class="popover" role="tooltip"><div class="arrow"></div><h3 class="popover-header"></h3><div class="popover-body"></div></div>',
	};

	has_content() {
		return this.get_title() || this.get_content();
	}

	set_content() {
		const $tip = $(this.get_tip());
		this.fill($tip.find(".popover-header"), this.get_title());
		let content = this.get_content();
		if (typeof content === "function") content = content.call(this.element);
		this.fill($tip.find(".popover-body"), content);
		$tip.removeClass("fade show");
	}

	get_content() {
		return this.element.getAttribute("data-content") || this.config.content;
	}
}

register(Popover);
