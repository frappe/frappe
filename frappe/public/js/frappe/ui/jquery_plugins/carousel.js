import {
	after_transition,
	call_method,
	get_selector,
	is_touch_device,
	reflow,
	trigger,
} from "./utils";

const DATA_KEY = "bs.carousel";
const EVENT_KEY = ".bs.carousel";
const SWIPE_THRESHOLD = 40;
const DEFAULTS = {
	interval: 5000,
	keyboard: true,
	slide: false,
	pause: "hover",
	wrap: true,
	touch: true,
};

class Carousel {
	constructor(element, config) {
		this.element = element;
		this.config = { ...DEFAULTS, ...config };
		this.interval = null;
		this.is_paused = false;
		this.is_sliding = false;
		this.indicators = element.querySelector(".carousel-indicators");
		this.add_listeners();
	}

	get items() {
		return [...this.element.querySelectorAll(".carousel-item")];
	}

	get active_item() {
		return this.element.querySelector(".active.carousel-item");
	}

	next() {
		if (!this.is_sliding) this.slide("next");
	}

	next_when_visible() {
		const $element = $(this.element);
		if (
			!document.hidden &&
			$element.is(":visible") &&
			$element.css("visibility") !== "hidden"
		) {
			this.next();
		}
	}

	prev() {
		if (!this.is_sliding) this.slide("prev");
	}

	pause(event) {
		if (!event) this.is_paused = true;
		if (this.element.querySelector(".carousel-item-next, .carousel-item-prev")) {
			trigger(this.element, "transitionend");
			this.cycle(true);
		}
		clearInterval(this.interval);
		this.interval = null;
	}

	cycle(event) {
		if (!event) this.is_paused = false;
		clearInterval(this.interval);
		this.interval = null;
		if (this.config.interval && !this.is_paused) {
			this.update_interval();
			this.interval = setInterval(
				() => (document.visibilityState ? this.next_when_visible() : this.next()),
				this.config.interval
			);
		}
	}

	to(index) {
		const items = this.items;
		const active_index = items.indexOf(this.active_item);
		if (index > items.length - 1 || index < 0) return;
		if (this.is_sliding) {
			$(this.element).one(`slid${EVENT_KEY}`, () => this.to(index));
			return;
		}
		if (active_index === index) {
			this.pause();
			this.cycle();
			return;
		}
		this.slide(index > active_index ? "next" : "prev", items[index]);
	}

	dispose() {
		$(this.element).off(EVENT_KEY);
		$.removeData(this.element, DATA_KEY);
		clearInterval(this.interval);
		this.element = this.indicators = this.interval = null;
	}

	add_listeners() {
		const $element = $(this.element);
		if (this.config.keyboard) {
			$element.on(`keydown${EVENT_KEY}`, (e) => {
				if (/input|textarea/i.test(e.target.tagName)) return;
				if (e.which === 37) {
					e.preventDefault();
					this.prev();
				} else if (e.which === 39) {
					e.preventDefault();
					this.next();
				}
			});
		}
		if (this.config.pause === "hover") {
			$element
				.on(`mouseenter${EVENT_KEY}`, (e) => this.pause(e))
				.on(`mouseleave${EVENT_KEY}`, (e) => this.cycle(e));
		}
		if (
			this.config.touch &&
			window.PointerEvent &&
			(is_touch_device() || navigator.maxTouchPoints > 0)
		) {
			this.add_swipe_listeners();
		}
	}

	add_swipe_listeners() {
		const is_touch = (e) => ["touch", "pen"].includes(e.originalEvent.pointerType);
		let start_x = 0;
		let delta_x = 0;
		$(this.element)
			.on(`dragstart${EVENT_KEY}`, ".carousel-item img", (e) => e.preventDefault())
			.on(`pointerdown${EVENT_KEY}`, (e) => {
				if (is_touch(e)) start_x = e.originalEvent.clientX;
			})
			.on(`pointerup${EVENT_KEY}`, (e) => {
				if (is_touch(e)) delta_x = e.originalEvent.clientX - start_x;
				if (Math.abs(delta_x) > SWIPE_THRESHOLD) {
					if (delta_x > 0) this.prev();
					else this.next();
				}
				delta_x = 0;
				if (this.config.pause === "hover") {
					this.pause();
					clearTimeout(this.touch_timeout);
					this.touch_timeout = setTimeout(
						() => this.cycle(),
						500 + this.config.interval
					);
				}
			});
		this.element.classList.add("pointer-event");
	}

	next_item(direction, active) {
		const items = this.items;
		const active_index = items.indexOf(active);
		const last = items.length - 1;
		if (
			!this.config.wrap &&
			((direction === "prev" && active_index === 0) ||
				(direction === "next" && active_index === last))
		) {
			return active;
		}
		const index = (active_index + (direction === "prev" ? -1 : 1)) % items.length;
		return index === -1 ? items[last] : items[index];
	}

	set_active_indicator(element) {
		if (!this.indicators) return;
		$(this.indicators).find(".active").removeClass("active");
		const indicator = this.indicators.children[this.items.indexOf(element)];
		indicator?.classList.add("active");
	}

	update_interval() {
		const element = this.active_item;
		if (!element) return;
		const interval = parseInt(element.getAttribute("data-interval"), 10);
		if (interval) {
			this.config.default_interval = this.config.default_interval || this.config.interval;
			this.config.interval = interval;
		} else {
			this.config.interval = this.config.default_interval || this.config.interval;
		}
	}

	slide(direction, element) {
		const active = this.active_item;
		const active_index = this.items.indexOf(active);
		const next = element || (active && this.next_item(direction, active));
		const next_index = this.items.indexOf(next);
		const is_cycling = Boolean(this.interval);
		const order_class = direction === "next" ? "carousel-item-left" : "carousel-item-right";
		const direction_class = direction === "next" ? "carousel-item-next" : "carousel-item-prev";
		const event_direction = direction === "next" ? "left" : "right";

		if (next && next.classList.contains("active")) {
			this.is_sliding = false;
			return;
		}
		const props = {
			relatedTarget: next,
			direction: event_direction,
			from: active_index,
			to: next_index,
		};
		if (trigger(this.element, `slide${EVENT_KEY}`, props).isDefaultPrevented()) return;
		if (!active || !next) return;

		this.is_sliding = true;
		if (is_cycling) this.pause();
		this.set_active_indicator(next);

		const done = () => {
			this.is_sliding = false;
			setTimeout(() => trigger(this.element, `slid${EVENT_KEY}`, props), 0);
		};

		if (this.element.classList.contains("slide")) {
			next.classList.add(direction_class);
			reflow(next);
			active.classList.add(order_class);
			next.classList.add(order_class);
			after_transition(active, () => {
				next.classList.remove(order_class, direction_class);
				next.classList.add("active");
				active.classList.remove("active", direction_class, order_class);
				done();
			});
		} else {
			active.classList.remove("active");
			next.classList.add("active");
			done();
		}

		if (is_cycling) this.cycle();
	}
}

$.fn.carousel = function (config) {
	return this.each(function () {
		let carousel = $(this).data(DATA_KEY);
		let options = { ...DEFAULTS, ...$(this).data() };
		if (typeof config === "object" && config) options = { ...options, ...config };
		const action = typeof config === "string" ? config : options.slide;

		if (!carousel) {
			carousel = new Carousel(this, options);
			$(this).data(DATA_KEY, carousel);
		}

		if (typeof config === "number") carousel.to(config);
		else if (typeof action === "string") call_method(carousel, action);
		else if (options.interval && options.ride) {
			carousel.pause();
			carousel.cycle();
		}
	});
};
$.fn.carousel.Constructor = Carousel;

$(document).on(`click${EVENT_KEY}.data-api`, "[data-slide], [data-slide-to]", function (e) {
	const selector = get_selector(this);
	const target = selector && $(selector)[0];
	if (!target || !target.classList.contains("carousel")) return;

	const config = { ...$(target).data(), ...$(this).data() };
	const slide_index = this.getAttribute("data-slide-to");
	if (slide_index) config.interval = false;

	$.fn.carousel.call($(target), config);
	if (slide_index) $(target).data(DATA_KEY).to(parseInt(slide_index, 10));
	e.preventDefault();
});

$(window).on(`load${EVENT_KEY}.data-api`, () => {
	$('[data-ride="carousel"]').each(function () {
		$.fn.carousel.call($(this), $(this).data());
	});
});
