import { after_transition, call_method, reflow, transition_duration, trigger } from "./utils";

const DATA_KEY = "bs.modal";
const EVENT_KEY = ".bs.modal";
const ESCAPE = 27;
const FIXED_CONTENT = ".fixed-top, .fixed-bottom, .is-fixed, .sticky-top";
const STICKY_CONTENT = ".sticky-top";
const DEFAULTS = { backdrop: true, keyboard: true, focus: true, show: true };

class Modal {
	constructor(element, config) {
		this._config = { ...DEFAULTS, ...config };
		this.element = element;
		this.dialog = element.querySelector(".modal-dialog");
		this._backdrop = null;
		this.is_shown = false;
		this.is_transitioning = false;
		this.is_body_overflowing = false;
		this.ignore_backdrop_click = false;
		this.scrollbar_width = 0;
	}

	get animated() {
		return this.element.classList.contains("fade");
	}

	toggle(related_target) {
		return this.is_shown ? this.hide() : this.show(related_target);
	}

	show(related_target) {
		if (this.is_shown || this.is_transitioning) return;
		if (
			trigger(this.element, `show${EVENT_KEY}`, {
				relatedTarget: related_target,
			}).isDefaultPrevented()
		) {
			return;
		}

		this.is_shown = true;
		if (this.animated) this.is_transitioning = true;

		this.measure_scrollbar();
		this.pad_for_scrollbar();
		this.handleUpdate();
		this.toggle_listeners();

		$(this.element).on(`click.dismiss${EVENT_KEY}`, '[data-dismiss="modal"]', (e) =>
			this.hide(e)
		);
		$(this.dialog).on(`mousedown.dismiss${EVENT_KEY}`, () => {
			$(this.element).one(`mouseup.dismiss${EVENT_KEY}`, (e) => {
				if (e.target === this.element) this.ignore_backdrop_click = true;
			});
		});

		this.toggle_backdrop(() => this.show_element(related_target));
	}

	hide(event) {
		event?.preventDefault();
		if (!this.is_shown || this.is_transitioning) return;
		if (trigger(this.element, `hide${EVENT_KEY}`).isDefaultPrevented() || !this.is_shown) {
			return;
		}

		this.is_shown = false;
		const animated = this.animated;
		if (animated) this.is_transitioning = true;

		this.toggle_listeners();
		$(document).off(`focusin${EVENT_KEY}`);
		this.element.classList.remove("show");
		$(this.element).off(`click.dismiss${EVENT_KEY}`);
		$(this.dialog).off(`mousedown.dismiss${EVENT_KEY}`);

		if (animated) after_transition(this.element, () => this.hide_element());
		else this.hide_element();
	}

	dispose() {
		[window, this.element, this.dialog].forEach((el) => $(el).off(EVENT_KEY));
		$(document).off(`focusin${EVENT_KEY}`);
		$.removeData(this.element, DATA_KEY);
		this.cancel_bounce?.();
		this._config = this.element = this.dialog = this._backdrop = null;
	}

	handleUpdate() {
		const overflowing = this.element.scrollHeight > document.documentElement.clientHeight;
		if (!this.is_body_overflowing && overflowing) {
			this.element.style.paddingLeft = `${this.scrollbar_width}px`;
		}
		if (this.is_body_overflowing && !overflowing) {
			this.element.style.paddingRight = `${this.scrollbar_width}px`;
		}
	}

	show_element(related_target) {
		const animated = this.animated;
		const body = this.dialog?.querySelector(".modal-body");

		if (this.element.parentNode?.nodeType !== Node.ELEMENT_NODE) {
			document.body.appendChild(this.element);
		}

		this.element.style.display = "block";
		this.element.removeAttribute("aria-hidden");
		this.element.setAttribute("aria-modal", true);
		this.element.setAttribute("role", "dialog");

		if (this.dialog?.classList.contains("modal-dialog-scrollable") && body) {
			body.scrollTop = 0;
		} else {
			this.element.scrollTop = 0;
		}

		if (animated) reflow(this.element);
		this.element.classList.add("show");
		if (this._config.focus) this.trap_focus();

		const shown = () => {
			if (this._config.focus) this.element.focus();
			this.is_transitioning = false;
			trigger(this.element, `shown${EVENT_KEY}`, { relatedTarget: related_target });
		};
		if (animated) after_transition(this.dialog, shown);
		else shown();
	}

	hide_element() {
		this.element.style.display = "none";
		this.element.setAttribute("aria-hidden", true);
		this.element.removeAttribute("aria-modal");
		this.element.removeAttribute("role");
		this.is_transitioning = false;
		this.toggle_backdrop(() => {
			document.body.classList.remove("modal-open");
			this.element.style.paddingLeft = "";
			this.element.style.paddingRight = "";
			this.reset_scrollbar_padding();
			trigger(this.element, `hidden${EVENT_KEY}`);
		});
	}

	trap_focus() {
		$(document)
			.off(`focusin${EVENT_KEY}`)
			.on(`focusin${EVENT_KEY}`, (e) => {
				if (
					e.target !== document &&
					e.target !== this.element &&
					!this.element.contains(e.target)
				) {
					this.element.focus();
				}
			});
	}

	toggle_listeners() {
		if (this.is_shown) {
			$(this.element).on(`keydown.dismiss${EVENT_KEY}`, (e) => {
				if (e.which !== ESCAPE) return;
				if (this._config.keyboard) {
					e.preventDefault();
					this.hide();
				} else {
					this.bounce();
				}
			});
			$(window).on(`resize${EVENT_KEY}`, () => this.handleUpdate());
		} else {
			$(this.element).off(`keydown.dismiss${EVENT_KEY}`);
			$(window).off(`resize${EVENT_KEY}`);
		}
	}

	bounce() {
		if (trigger(this.element, `hidePrevented${EVENT_KEY}`).isDefaultPrevented()) return;

		const overflowing = this.element.scrollHeight > document.documentElement.clientHeight;
		if (!overflowing) this.element.style.overflowY = "hidden";
		this.element.classList.add("modal-static");

		this.cancel_bounce?.();
		this.cancel_bounce = after_transition(
			this.element,
			() => {
				this.element.classList.remove("modal-static");
				if (overflowing) return;
				this.cancel_bounce = after_transition(
					this.element,
					() => (this.element.style.overflowY = ""),
					0
				);
			},
			transition_duration(this.dialog)
		);
		this.element.focus();
	}

	toggle_backdrop(callback) {
		const animated = this.animated;

		if (this.is_shown && this._config.backdrop) {
			this._backdrop = document.createElement("div");
			this._backdrop.className = "modal-backdrop";
			if (animated) this._backdrop.classList.add("fade");
			document.body.appendChild(this._backdrop);

			$(this.element).on(`click.dismiss${EVENT_KEY}`, (e) => {
				if (this.ignore_backdrop_click) {
					this.ignore_backdrop_click = false;
					return;
				}
				if (e.target !== e.currentTarget) return;
				if (this._config.backdrop === "static") this.bounce();
				else this.hide();
			});

			if (animated) reflow(this._backdrop);
			this._backdrop.classList.add("show");

			if (!callback) return;
			if (animated) after_transition(this._backdrop, callback);
			else callback();
		} else if (!this.is_shown && this._backdrop) {
			this._backdrop.classList.remove("show");
			const remove = () => {
				this._backdrop?.remove();
				this._backdrop = null;
				callback?.();
			};
			if (animated) after_transition(this._backdrop, remove);
			else remove();
		} else {
			callback?.();
		}
	}

	measure_scrollbar() {
		const rect = document.body.getBoundingClientRect();
		this.is_body_overflowing = Math.round(rect.left + rect.right) < window.innerWidth;

		const probe = document.createElement("div");
		probe.className = "modal-scrollbar-measure";
		document.body.appendChild(probe);
		this.scrollbar_width = probe.getBoundingClientRect().width - probe.clientWidth;
		probe.remove();
	}

	pad_for_scrollbar() {
		if (this.is_body_overflowing) {
			const width = this.scrollbar_width;
			const adjust = (element, prop, sign) => {
				const css = prop === "paddingRight" ? "padding-right" : "margin-right";
				$(element)
					.data(css, element.style[prop])
					.css(css, `${parseFloat($(element).css(css)) + sign * width}px`);
			};
			document
				.querySelectorAll(FIXED_CONTENT)
				.forEach((el) => adjust(el, "paddingRight", 1));
			document
				.querySelectorAll(STICKY_CONTENT)
				.forEach((el) => adjust(el, "marginRight", -1));
			adjust(document.body, "paddingRight", 1);
		}
		document.body.classList.add("modal-open");
	}

	reset_scrollbar_padding() {
		document.querySelectorAll(FIXED_CONTENT).forEach((el) => {
			const padding = $(el).data("padding-right");
			$(el).removeData("padding-right");
			el.style.paddingRight = padding || "";
		});
		document.querySelectorAll(STICKY_CONTENT).forEach((el) => {
			const margin = $(el).data("margin-right");
			if (margin !== undefined) $(el).css("margin-right", margin).removeData("margin-right");
		});
		const padding = $(document.body).data("padding-right");
		$(document.body).removeData("padding-right");
		document.body.style.paddingRight = padding || "";
	}
}

$.fn.modal = function (config, related_target) {
	return this.each(function () {
		let modal = $(this).data(DATA_KEY);
		const options = {
			...DEFAULTS,
			...$(this).data(),
			...(typeof config === "object" && config ? config : {}),
		};
		if (!modal) {
			modal = new Modal(this, options);
			$(this).data(DATA_KEY, modal);
		}
		if (typeof config === "string") call_method(modal, config, related_target);
		else if (options.show) modal.show(related_target);
	});
};
$.fn.modal.Constructor = Modal;
