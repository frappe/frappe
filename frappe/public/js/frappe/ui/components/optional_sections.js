frappe.provide("frappe.ui");

/**
 * @typedef {Object} OptionalSectionOpts
 * @property {string} title Section heading, also the label of its add button. Rendered as text, never HTML.
 * @property {Element|JQuery|function|string} [content] The section body. An element (or a function returning one — called once, the first time the section is added) is the rich channel; a plain string renders as text, never HTML.
 * @property {boolean} [added] Start with the section already shown.
 */

/**
 * @typedef {Object} OptionalSectionsOpts
 * @property {OptionalSectionOpts[]} sections
 * @property {string} [label] Text above the add buttons, e.g. __("Add more now").
 * @property {string} [remove_label] Label of each section's remove button. Defaults to __("Remove").
 * @property {function} [on_add] Called with (index, section) after a section is added.
 * @property {function} [on_remove] Called with (index, section) after a section is removed. Removing only hides the section and keeps its content, so reset any inputs here.
 * @property {string} [css_class] Extra classes on the root.
 */

/**
 * Optional sections a person adds only when they need them: a row of
 * add buttons, one per section, and the added sections shown inline in
 * their declared order, each with a remove button that puts its add
 * button back. For forms where most inputs are optional and showing them
 * all at once would bury the required ones. Load it first with
 * `await frappe.require(["optional_sections.bundle.js", "optional_sections.bundle.css"])`.
 * @example
 * const sections = new frappe.ui.OptionalSections({
 *     label: __("Add more now"),
 *     sections: [
 *         { title: __("Contact"), content: () => this.make_contact_fields() },
 *         { title: __("Bank"), content: () => this.make_bank_fields() },
 *     ],
 *     on_remove: (i) => this.clear_fields(i),
 * });
 * body.append(sections.$el);
 */
frappe.ui.OptionalSections = class OptionalSections {
	/** @param {OptionalSectionsOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.el = document.createElement("div");
		this.el.className = ["es-optional-sections", opts.css_class].filter(Boolean).join(" ");

		this.more = document.createElement("div");
		this.more.className = "es-optional-sections__more";
		if (opts.label) {
			const label = document.createElement("div");
			label.className = "es-optional-sections__label";
			label.textContent = opts.label;
			this.more.appendChild(label);
		}
		this.buttons = document.createElement("div");
		this.buttons.className = "es-optional-sections__buttons";
		this.buttons.setAttribute("role", "group");
		if (opts.label) this.buttons.setAttribute("aria-label", opts.label);
		this.more.appendChild(this.buttons);

		this.sections = (opts.sections || []).map((section, i) => {
			const root = document.createElement("section");
			root.className = "es-optional-sections__section";

			const head = document.createElement("div");
			head.className = "es-optional-sections__head";
			const title = document.createElement("div");
			title.className = "es-optional-sections__title";
			title.setAttribute("role", "heading");
			title.setAttribute("aria-level", "3");
			title.textContent = section.title || "";
			head.appendChild(title);
			head.appendChild(
				frappe.ui.button({
					label: opts.remove_label || __("Remove"),
					variant: "ghost",
					size: "sm",
					onclick: () => this.remove(i),
				})[0]
			);

			const body = document.createElement("div");
			body.className = "es-optional-sections__body";
			root.append(head, body);
			this.el.appendChild(root);

			const add_button = frappe.ui.button({
				label: section.title || "",
				icon: "plus",
				variant: "outline",
				size: "sm",
				onclick: () => this.add(i),
			})[0];
			this.buttons.appendChild(add_button);

			return { section, root, body, add_button, rendered: false };
		});
		this.el.appendChild(this.more);

		for (const entry of this.sections) {
			this.set_state(entry, !!entry.section.added);
		}
		this.$el = $(this.el);
	}

	render_body(entry) {
		if (entry.rendered) return;
		entry.rendered = true;
		let content = entry.section.content;
		if (typeof content === "function") content = content(this);
		if (typeof content === "string") {
			entry.body.textContent = content;
		} else if (content) {
			const el = $(content)[0];
			el && entry.body.appendChild(el);
		}
	}

	set_state(entry, added) {
		if (added) this.render_body(entry);
		entry.root.setAttribute("data-state", added ? "added" : "removed");
		entry.root.hidden = !added;
		entry.add_button.hidden = added;
		this.more.hidden = this.sections.every((other) => other.add_button.hidden);
	}

	add(index) {
		const entry = this.sections[index];
		if (!entry || this.is_added(index)) return;
		this.set_state(entry, true);
		const focusable = entry.body.querySelector(
			"input:not([type=checkbox]):not([type=hidden]), select, textarea"
		);
		(focusable || entry.root.querySelector(".es-button"))?.focus();
		this.opts.on_add && this.opts.on_add(index, entry.section);
	}

	remove(index) {
		const entry = this.sections[index];
		if (!entry || !this.is_added(index)) return;
		this.set_state(entry, false);
		entry.add_button.focus();
		this.opts.on_remove && this.opts.on_remove(index, entry.section);
	}

	is_added(index) {
		return this.sections[index]?.root.getAttribute("data-state") === "added";
	}

	destroy() {
		this.el.remove();
	}
};

/**
 * Convenience form: build the sections and get the root element back, so
 * it chains inside append(...) calls. The instance is on
 * `.data("es-optional-sections")` when you need add/remove/is_added.
 * @param {OptionalSectionsOpts} opts
 * @returns {JQuery}
 * @example body.append(frappe.ui.optional_sections({ label: __("Add more now"), sections: [...] }));
 */
frappe.ui.optional_sections = function (opts = {}) {
	const sections = new frappe.ui.OptionalSections(opts);
	sections.$el.data("es-optional-sections", sections);
	return sections.$el;
};

export default frappe.ui.optional_sections;
