const FIXED_CONTENT = ".fixed-top, .fixed-bottom, .is-fixed, .sticky-top";
const STICKY_CONTENT = ".sticky-top";

const reflow = (element) => element.offsetHeight;

function transition_duration(element) {
	if (!element) return 0;
	const style = getComputedStyle(element);
	const duration = parseFloat(style.transitionDuration) || 0;
	const delay = parseFloat(style.transitionDelay) || 0;
	return (duration + delay) * 1000;
}

function after_transition(element, callback, duration = transition_duration(element)) {
	let timer;
	const done = (event) => {
		if (event && event.target !== element) return;
		cancel();
		callback();
	};
	const cancel = () => {
		element.removeEventListener("transitionend", done);
		clearTimeout(timer);
	};
	element.addEventListener("transitionend", done);
	timer = setTimeout(done, duration);
	return cancel;
}

/**
 * @typedef {Object} ModalConfig
 * @property {boolean|"static"} [backdrop=true] "static" bounces instead of closing on a backdrop click.
 * @property {boolean} [keyboard=true] Escape closes; false bounces.
 * @property {boolean} [focus=true] Focus the modal on show and keep focus inside until release_focus().
 * @property {string} [dismiss] Selector of elements inside the modal that close it on click.
 * @property {function} [on_show] Called before the modal opens.
 * @property {function} [on_shown] Called once it is open and the animation ended.
 * @property {function} [on_hide] Called before it closes.
 * @property {function} [on_hidden] Called once it is closed and the backdrop is gone.
 */
export default class Modal {
	/**
	 * @param {Element} element The `.modal` element.
	 * @param {ModalConfig} config
	 */
	constructor(element, config = {}) {
		this.config = { backdrop: true, keyboard: true, focus: true, ...config };
		this.element = element;
		this.dialog = element.querySelector(".modal-dialog");
		this.backdrop = null;
		this.is_shown = false;
		this.is_transitioning = false;
		this.ignore_backdrop_click = false;
		this.padded = [];
	}

	get animated() {
		return this.element.classList.contains("fade");
	}

	show() {
		if (this.is_shown || this.is_transitioning) return;
		this.config.on_show?.();

		this.is_shown = true;
		if (this.animated) this.is_transitioning = true;

		this.measure_scrollbar();
		this.pad_for_scrollbar();
		this.adjust_padding();
		this.toggle_listeners();

		if (this.config.dismiss) {
			$(this.element).on("click.dismiss.modal", this.config.dismiss, (e) => this.hide(e));
		}
		$(this.dialog).on("mousedown.dismiss.modal", () => {
			$(this.element).one("mouseup.dismiss.modal", (e) => {
				if (e.target === this.element) this.ignore_backdrop_click = true;
			});
		});

		this.toggle_backdrop(() => this.show_element());
	}

	hide(event) {
		event?.preventDefault();
		if (!this.is_shown || this.is_transitioning) return;
		this.config.on_hide?.();
		if (!this.is_shown) return;

		this.is_shown = false;
		const animated = this.animated;
		if (animated) this.is_transitioning = true;

		this.toggle_listeners();
		this.release_focus();
		this.element.classList.remove("show");
		$(this.element).off(".dismiss.modal");
		$(this.dialog).off(".dismiss.modal");

		if (animated) after_transition(this.element, () => this.hide_element());
		else this.hide_element();
	}

	adjust_padding() {
		const overflowing = this.element.scrollHeight > document.documentElement.clientHeight;
		if (!this.is_body_overflowing && overflowing) {
			this.element.style.paddingLeft = `${this.scrollbar_width}px`;
		}
		if (this.is_body_overflowing && !overflowing) {
			this.element.style.paddingRight = `${this.scrollbar_width}px`;
		}
	}

	show_element() {
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

		if (this.animated) reflow(this.element);
		this.element.classList.add("show");
		if (this.config.focus) this.trap_focus();

		const shown = () => {
			if (this.config.focus) this.element.focus();
			this.is_transitioning = false;
			this.config.on_shown?.();
		};
		if (this.animated) after_transition(this.dialog, shown);
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
			this.config.on_hidden?.();
		});
	}

	trap_focus() {
		$(document)
			.off("focusin.modal")
			.on("focusin.modal", (e) => {
				if (
					e.target !== document &&
					e.target !== this.element &&
					!this.element.contains(e.target)
				) {
					this.element.focus();
				}
			});
	}

	release_focus() {
		$(document).off("focusin.modal");
	}

	toggle_listeners() {
		if (this.is_shown) {
			$(this.element).on("keydown.dismiss.modal", (e) => {
				if (e.key !== "Escape") return;
				if (this.config.keyboard) {
					e.preventDefault();
					this.hide();
				} else {
					this.bounce();
				}
			});
			$(window).on("resize.modal", () => this.adjust_padding());
		} else {
			$(this.element).off("keydown.dismiss.modal");
			$(window).off("resize.modal");
		}
	}

	bounce() {
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

		if (this.is_shown && this.config.backdrop) {
			this.backdrop = document.createElement("div");
			this.backdrop.className = "modal-backdrop";
			if (animated) this.backdrop.classList.add("fade");
			document.body.appendChild(this.backdrop);

			$(this.element).on("click.dismiss.modal", (e) => {
				if (this.ignore_backdrop_click) {
					this.ignore_backdrop_click = false;
					return;
				}
				if (e.target !== e.currentTarget) return;
				if (this.config.backdrop === "static") this.bounce();
				else this.hide();
			});

			if (animated) reflow(this.backdrop);
			this.backdrop.classList.add("show");

			if (animated) after_transition(this.backdrop, callback);
			else callback();
		} else if (!this.is_shown && this.backdrop) {
			this.backdrop.classList.remove("show");
			const remove = () => {
				this.backdrop?.remove();
				this.backdrop = null;
				callback();
			};
			if (animated) after_transition(this.backdrop, remove);
			else remove();
		} else {
			callback();
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
			const adjust = (element, prop, sign) => {
				this.padded.push([element, prop, element.style[prop]]);
				const current = parseFloat(getComputedStyle(element)[prop]) || 0;
				element.style[prop] = `${current + sign * this.scrollbar_width}px`;
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
		for (const [element, prop, value] of this.padded) element.style[prop] = value;
		this.padded = [];
	}
}
