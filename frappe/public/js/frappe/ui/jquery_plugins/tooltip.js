import { Anchor } from "./anchor";
import { ALLOWED_TAGS, sanitize_html } from "./sanitize";
import {
	after_transition,
	call_method,
	is_element,
	is_touch_device,
	trigger,
	unique_id,
} from "./utils";

const UNSAFE_DATA_OPTIONS = ["sanitize", "whiteList", "sanitizeFn"];
const SIDES = ["auto", "top", "right", "bottom", "left"];

export class Tooltip {
	static NAME = "tooltip";
	static DATA_KEY = "bs.tooltip";
	static EVENT_KEY = ".bs.tooltip";
	static CLASS_PREFIX = "bs-tooltip";
	static DEFAULTS = {
		animation: true,
		template:
			'<div class="tooltip" role="tooltip"><div class="arrow"></div><div class="tooltip-inner"></div></div>',
		trigger: "hover focus",
		title: "",
		delay: 0,
		html: false,
		placement: "top",
		offset: 0,
		container: false,
		boundary: "scrollParent",
		customClass: "",
		sanitize: true,
		sanitizeFn: null,
		whiteList: ALLOWED_TAGS,
	};

	constructor(element, config) {
		this.is_enabled = true;
		this.timeout = 0;
		this.hover_state = "";
		this.active_triggers = {};
		this.anchor = null;
		this.element = element;
		this.config = this.get_config(config);
		this.tip = null;
		this.listen();
	}

	event(name) {
		return `${name}${this.constructor.EVENT_KEY}`;
	}

	enable() {
		this.is_enabled = true;
	}

	disable() {
		this.is_enabled = false;
	}

	toggleEnabled() {
		this.is_enabled = !this.is_enabled;
	}

	toggle(event) {
		if (!this.is_enabled) return;
		if (event) {
			this.active_triggers.click = !this.active_triggers.click;
			if (this.has_active_trigger()) this.enter();
			else this.leave();
		} else if (this.get_tip().classList.contains("show")) {
			this.leave();
		} else {
			this.enter();
		}
	}

	dispose() {
		clearTimeout(this.timeout);
		$.removeData(this.element, this.constructor.DATA_KEY);
		$(this.element).off(this.constructor.EVENT_KEY);
		$(this.element).closest(".modal").off("hide.bs.modal", this.hide_with_modal);
		$(this.tip).remove();
		this.anchor?.destroy();
		this.anchor = this.element = this.config = this.tip = null;
	}

	show() {
		if ($(this.element).css("display") === "none") {
			throw new Error("Please use show on visible elements");
		}
		if (!this.has_content() || !this.is_enabled) return;

		const show_event = trigger(this.element, this.event("show"));
		const root = this.element.getRootNode();
		const in_dom = (root instanceof ShadowRoot ? root : document.documentElement).contains(
			this.element
		);
		if (show_event.isDefaultPrevented() || !in_dom) return;

		const tip = this.get_tip();
		const id = unique_id(this.constructor.NAME);
		tip.setAttribute("id", id);
		this.element.setAttribute("aria-describedby", id);
		this.set_content();
		if (this.config.animation) tip.classList.add("fade");

		const placement =
			typeof this.config.placement === "function"
				? this.config.placement.call(this, tip, this.element)
				: this.config.placement;
		const side = this.get_side(placement);
		this.add_side_class(side);

		$(tip).data(this.constructor.DATA_KEY, this);
		if (!document.documentElement.contains(tip)) $(tip).appendTo(this.get_container());
		trigger(this.element, this.event("inserted"));

		this.anchor = new Anchor(this.element, tip, {
			placement: side,
			offset: this.config.offset,
			boundary: this.config.boundary,
			arrow: ".arrow",
			on_create: (data) => {
				if (data.original_placement !== data.placement) this.on_placement_change(data);
			},
			on_update: (data) => this.on_placement_change(data),
		});
		tip.classList.add("show");
		$(tip).addClass(this.config.customClass);
		if (is_touch_device()) $(document.body).children().on("mouseover", null, $.noop);

		const complete = () => {
			if (this.config.animation) this.fix_transition();
			const previous_state = this.hover_state;
			this.hover_state = null;
			trigger(this.element, this.event("shown"));
			if (previous_state === "out") this.leave();
		};
		if (tip.classList.contains("fade")) after_transition(tip, complete);
		else complete();
	}

	hide(callback) {
		const tip = this.get_tip();
		const complete = () => {
			if (this.hover_state !== "show") tip.parentNode?.removeChild(tip);
			this.remove_side_class();
			this.element.removeAttribute("aria-describedby");
			trigger(this.element, this.event("hidden"));
			this.anchor?.destroy();
			callback?.();
		};

		if (trigger(this.element, this.event("hide")).isDefaultPrevented()) return;

		tip.classList.remove("show");
		if (is_touch_device()) $(document.body).children().off("mouseover", null, $.noop);
		this.active_triggers = { click: false, focus: false, hover: false };

		if (this.tip.classList.contains("fade")) after_transition(tip, complete);
		else complete();
		this.hover_state = "";
	}

	update() {
		this.anchor?.schedule_update();
	}

	has_content() {
		return Boolean(this.get_title());
	}

	get_tip() {
		this.tip = this.tip || $(this.config.template)[0];
		return this.tip;
	}

	set_content() {
		const tip = this.get_tip();
		this.fill($(tip.querySelectorAll(".tooltip-inner")), this.get_title());
		tip.classList.remove("fade", "show");
	}

	fill($target, content) {
		if (typeof content === "object" && (content.nodeType || content.jquery)) {
			if (!this.config.html) $target.text($(content).text());
			else if (!$(content).parent().is($target)) $target.empty().append(content);
			return;
		}
		if (!this.config.html) {
			$target.text(content);
			return;
		}
		if (this.config.sanitize) {
			content = sanitize_html(content, this.config.whiteList, this.config.sanitizeFn);
		}
		$target.html(content);
	}

	get_title() {
		const title = this.element.getAttribute("data-original-title");
		if (title) return title;
		return typeof this.config.title === "function"
			? this.config.title.call(this.element)
			: this.config.title;
	}

	get_side(placement) {
		return SIDES.find((side) => side === placement.toLowerCase());
	}

	add_side_class(side) {
		this.get_tip().classList.add(`${this.constructor.CLASS_PREFIX}-${side}`);
	}

	remove_side_class() {
		const prefix = this.constructor.CLASS_PREFIX;
		const tip = this.get_tip();
		for (const name of [...tip.classList]) {
			if (name.startsWith(prefix)) tip.classList.remove(name);
		}
	}

	on_placement_change(data) {
		this.tip = data.popper;
		this.remove_side_class();
		this.add_side_class(this.get_side(data.placement));
	}

	get_container() {
		const { container } = this.config;
		if (container === false) return document.body;
		if (is_element(container)) return $(container);
		return $(document).find(container);
	}

	listen() {
		for (const name of this.config.trigger.split(" ")) {
			if (name === "click") {
				$(this.element).on(this.event("click"), (e) => this.toggle(e));
			} else if (name !== "manual") {
				const [event_in, event_out] =
					name === "hover" ? ["mouseenter", "mouseleave"] : ["focusin", "focusout"];
				$(this.element)
					.on(this.event(event_in), (e) => this.enter(e))
					.on(this.event(event_out), (e) => this.leave(e));
			}
		}

		this.hide_with_modal = () => this.element && this.hide();
		$(this.element).closest(".modal").on("hide.bs.modal", this.hide_with_modal);
		this.move_title();
	}

	move_title() {
		const title = this.element.getAttribute("title");
		if (title || typeof this.element.getAttribute("data-original-title") !== "string") {
			this.element.setAttribute("data-original-title", title || "");
			this.element.setAttribute("title", "");
		}
	}

	enter(event) {
		if (event) this.active_triggers[event.type === "focusin" ? "focus" : "hover"] = true;
		if (this.get_tip().classList.contains("show") || this.hover_state === "show") {
			this.hover_state = "show";
			return;
		}

		clearTimeout(this.timeout);
		this.hover_state = "show";
		if (!this.config.delay?.show) {
			this.show();
			return;
		}
		this.timeout = setTimeout(() => {
			if (this.hover_state === "show") this.show();
		}, this.config.delay.show);
	}

	leave(event) {
		if (event) this.active_triggers[event.type === "focusout" ? "focus" : "hover"] = false;
		if (this.has_active_trigger()) return;

		clearTimeout(this.timeout);
		this.hover_state = "out";
		if (!this.config.delay?.hide) {
			this.hide();
			return;
		}
		this.timeout = setTimeout(() => {
			if (this.hover_state === "out") this.hide();
		}, this.config.delay.hide);
	}

	has_active_trigger() {
		return Object.values(this.active_triggers).some(Boolean);
	}

	get_config(config) {
		const data = { ...$(this.element).data() };
		for (const key of UNSAFE_DATA_OPTIONS) delete data[key];

		config = {
			...this.constructor.DEFAULTS,
			...data,
			...(typeof config === "object" && config ? config : {}),
		};
		if (typeof config.delay === "number") {
			config.delay = { show: config.delay, hide: config.delay };
		}
		if (typeof config.title === "number") config.title = config.title.toString();
		if (typeof config.content === "number") config.content = config.content.toString();
		if (config.sanitize) {
			config.template = sanitize_html(config.template, config.whiteList, config.sanitizeFn);
		}
		return config;
	}

	fix_transition() {
		const tip = this.get_tip();
		if (tip.getAttribute("x-placement") !== null) return;

		const animation = this.config.animation;
		tip.classList.remove("fade");
		this.config.animation = false;
		this.hide();
		this.show();
		this.config.animation = animation;
	}
}

export function register(Plugin) {
	const { NAME, DATA_KEY } = Plugin;
	$.fn[NAME] = function (config) {
		return this.each(function () {
			let plugin = $(this).data(DATA_KEY);
			if (!plugin && /dispose|hide/.test(config)) return;
			if (!plugin) {
				plugin = new Plugin(this, typeof config === "object" ? config : null);
				$(this).data(DATA_KEY, plugin);
			}
			if (typeof config === "string") call_method(plugin, config);
		});
	};
	$.fn[NAME].Constructor = Plugin;
}

register(Tooltip);
