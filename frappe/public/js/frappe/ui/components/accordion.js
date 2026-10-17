import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} AccordionItemOpts
 * @property {string} title Heading text. Rendered as text, never HTML.
 * @property {string} [description] Second line under the title, as text. Change it later with set_description.
 * @property {string} [icon] Lucide icon name shown before the title.
 * @property {Element|JQuery|function|string} [content] The section body. An element (or a function returning one — called once, on first open) is the rich channel; a plain string renders as text, never HTML.
 * @property {boolean} [open] Start expanded. In "single" mode only the first open item counts.
 * @property {boolean} [disabled] Inert header, skipped by keyboard navigation.
 */

/**
 * @typedef {Object} AccordionOpts
 * @property {AccordionItemOpts[]} items
 * @property {"single"|"multiple"} [type="single"] "single" keeps at most one section open; "multiple" lets them open independently.
 * @property {boolean} [collapsible=true] In "single" mode, whether the open section can be closed again.
 * @property {function} [on_change] Called with (index, open, item) when a section opens or closes. Not called for the initial state.
 * @property {string} [css_class] Extra classes on the root.
 */

const TYPES = ["single", "multiple"];

let id_counter = 0;

/**
 * Stacked sections that expand and collapse in place — for optional or
 * secondary content that should stay one click away without taking room
 * (to switch between views of the same thing, use frappe.ui.Tabs). Follows
 * the accordion pattern: each header is a button with aria-expanded,
 * ArrowUp/Down move between headers, Home/End jump. A section's content
 * function runs once, on first open, so heavy sections don't render until
 * someone looks at them.
 * @example
 * const accordion = new frappe.ui.Accordion({
 *     type: "multiple",
 *     items: [
 *         { title: __("Contact"), icon: "phone", content: () => this.render_contact() },
 *         { title: __("Bank"), icon: "landmark", content: () => this.render_bank() },
 *     ],
 *     on_change: (i, open) => open && this.focus_first(i),
 * });
 * body.append(accordion.$el);
 */
frappe.ui.Accordion = class Accordion {
	/** @param {AccordionOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.type = validated(opts.type, TYPES, "type", "accordion") || "single";
		this.collapsible = opts.collapsible !== false;

		const uid = ++id_counter;
		this.el = document.createElement("div");
		this.el.className = ["es-accordion", opts.css_class].filter(Boolean).join(" ");
		this.el.setAttribute("data-type", this.type);

		this.items = (opts.items || []).map((item, i) => {
			const root = document.createElement("div");
			root.className = "es-accordion__item";

			const header = document.createElement("div");
			header.className = "es-accordion__header";
			header.setAttribute("role", "heading");
			header.setAttribute("aria-level", "3");

			const trigger = document.createElement("button");
			trigger.type = "button";
			trigger.className = "es-accordion__trigger";
			trigger.id = `es-accordion-${uid}-${i}`;
			if (item.disabled) trigger.disabled = true;
			if (item.icon) {
				trigger.insertAdjacentHTML("beforeend", frappe.utils.icon(item.icon, "sm"));
			}

			const text = document.createElement("span");
			text.className = "es-accordion__text";
			const title = document.createElement("span");
			title.className = "es-accordion__title";
			title.textContent = item.title || "";
			const description = document.createElement("span");
			description.className = "es-accordion__description";
			text.append(title, description);
			trigger.appendChild(text);
			trigger.insertAdjacentHTML(
				"beforeend",
				`<span class="es-accordion__chevron" aria-hidden="true">${frappe.utils.icon(
					"chevron-down",
					"sm"
				)}</span>`
			);
			header.appendChild(trigger);

			const content = document.createElement("div");
			content.className = "es-accordion__content";
			content.id = `es-accordion-content-${uid}-${i}`;
			content.setAttribute("role", "region");
			content.setAttribute("aria-labelledby", trigger.id);
			const body = document.createElement("div");
			body.className = "es-accordion__body";
			content.appendChild(body);
			trigger.setAttribute("aria-controls", content.id);

			root.append(header, content);
			this.el.appendChild(root);

			const entry = { item, root, trigger, content, body, description, rendered: false };
			this.set_description_text(entry, item.description);
			trigger.addEventListener("click", () => this.toggle(i));
			return entry;
		});

		this.el.addEventListener("keydown", (e) => {
			if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
			const enabled = this.items.filter((entry) => !entry.item.disabled);
			const current = enabled.findIndex((entry) => entry.trigger === e.target);
			if (current === -1) return;

			let target;
			if (e.key === "Home") target = enabled[0];
			else if (e.key === "End") target = enabled[enabled.length - 1];
			else {
				const step = e.key === "ArrowDown" ? 1 : -1;
				target = enabled[(current + step + enabled.length) % enabled.length];
			}
			e.preventDefault();
			target.trigger.focus();
		});

		let opened = this.items.filter((entry) => entry.item.open && !entry.item.disabled);
		if (this.type === "single") opened = opened.slice(0, 1);
		for (const entry of this.items) {
			this.set_state(entry, opened.includes(entry));
		}
		this.$el = $(this.el);
	}

	render_body(entry) {
		if (entry.rendered) return;
		entry.rendered = true;
		let content = entry.item.content;
		if (typeof content === "function") content = content(this);
		if (typeof content === "string") {
			entry.body.textContent = content;
		} else if (content) {
			const el = $(content)[0];
			el && entry.body.appendChild(el);
		}
	}

	set_state(entry, open) {
		if (open) this.render_body(entry);
		const state = open ? "open" : "closed";
		entry.root.setAttribute("data-state", state);
		entry.trigger.setAttribute("data-state", state);
		entry.trigger.setAttribute("aria-expanded", open ? "true" : "false");
		entry.content.setAttribute("data-state", state);
		entry.content.inert = !open;
		const locked = open && this.type === "single" && !this.collapsible;
		entry.trigger.toggleAttribute("aria-disabled", locked);
	}

	set_description_text(entry, text) {
		entry.description.textContent = text || "";
		entry.description.hidden = !text;
	}

	toggle(index) {
		return this.is_open(index) ? this.close(index) : this.open(index);
	}

	open(index) {
		const entry = this.items[index];
		if (!entry || entry.item.disabled || this.is_open(index)) return;
		if (this.type === "single") {
			this.items.forEach(
				(other, i) => i !== index && this.is_open(i) && this.close(i, true)
			);
		}
		this.set_state(entry, true);
		this.opts.on_change && this.opts.on_change(index, true, entry.item);
	}

	close(index, force = false) {
		const entry = this.items[index];
		if (!entry || !this.is_open(index)) return;
		if (!force && this.type === "single" && !this.collapsible) return;
		this.set_state(entry, false);
		this.opts.on_change && this.opts.on_change(index, false, entry.item);
	}

	is_open(index) {
		return this.items[index]?.root.getAttribute("data-state") === "open";
	}

	/** Change the second line under a section's title, e.g. a summary of what's filled in. */
	set_description(index, text) {
		const entry = this.items[index];
		entry && this.set_description_text(entry, text);
	}

	destroy() {
		this.el.remove();
	}
};

/**
 * Convenience form: build the accordion and get the root element back, so
 * it chains inside append(...) calls. The instance is on
 * `.data("es-accordion")` when you need open/close/set_description.
 * @param {AccordionOpts} opts
 * @returns {JQuery}
 * @example body.append(frappe.ui.accordion({ items: [...] }));
 */
frappe.ui.accordion = function (opts = {}) {
	const accordion = new frappe.ui.Accordion(opts);
	accordion.$el.data("es-accordion", accordion);
	return accordion.$el;
};

export default frappe.ui.accordion;
