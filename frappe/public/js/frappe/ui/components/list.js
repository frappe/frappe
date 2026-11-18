import { validated, safe_attrs, safe_href, icon_html } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ListAction
 * Button shown at the end of a row while it is hovered or focused. `onclick` gets the item
 * and the list; return a promise to keep the button busy until it settles.
 * @property {string} label Translated text. Rendered as text, never HTML.
 * @property {"subtle"|"ghost"|"outline"} [variant="subtle"]
 * @property {"gray"|"red"} [theme="gray"]
 * @property {(item:ListItem, list:List)=>any} onclick
 *
 * @typedef {Object} ListItem
 * @property {string} id Unique across the whole list.
 * @property {string} [group] Id of the group the row sits under, when the list has `groups`.
 * @property {string} title Translated text. Rendered as text, never HTML.
 * @property {string} [subtitle] Muted second line.
 * @property {string} [meta] Muted text at the end of the row, e.g. a date. Hidden on narrow lists and while the row shows its actions.
 * @property {{label:string, image?:string}} [avatar] Picture at the start of the row.
 * @property {string} [icon] Lucide icon name at the start of the row, used when there is no avatar.
 * @property {{label:string, theme?:"gray"|"blue"|"green"|"amber"|"red"|"violet"}} [badge] Status next to the meta.
 * @property {string} [href] Renders the row as a link, so cmd-click and middle-click work. Code-running schemes are refused.
 * @property {ListAction[]} [actions]
 * @property {(item:ListItem, list:List)=>Node|JQuery|Array<Node|JQuery|null>} [controls] Always-visible controls (a status dropdown, a button) at the end of the row, after the badge and meta and before the hover actions. Called again whenever the row is re-rendered. Clicks inside never open the row or follow its link; the controls stay in the tab order.
 *
 * @typedef {Object} ListGroup
 * @property {string} id Matches the items' `group`.
 * @property {string} label Translated text. Rendered as text, never HTML.
 * @property {number} [count] Shown after the label, e.g. the group's total beyond the loaded rows.
 *
 * @typedef {Object} ListOpts
 * @property {ListItem[]} items
 * @property {ListGroup[]} [groups] Rows go under a heading per group, in this order; a group without rows is left out, and so are items outside every group.
 * @property {string} [selected] Id of the highlighted row. The list never selects on its own click; change it with `set_selected`.
 * @property {"boxed"|"flat"} [variant="boxed"] "flat" drops the border and padding, for lists that sit inside a pane or card.
 * @property {number} [max] Shows this many rows and a footer button that reveals the rest.
 * @property {string} [more_label="Show all {0}"] Footer button text. {0} is the number of rows.
 * @property {EmptyStateOpts} [empty] Shown instead of the box when there are no items.
 * @property {(item:ListItem, list:List, event:Event)=>void} [on_click] Runs when a row is clicked or activated with Enter or Space. On link rows it is skipped for cmd/ctrl/shift/alt clicks, and the link still opens unless you call event.preventDefault() to handle the click yourself.
 * @property {string} [css_class] Extra classes on the root.
 * @property {Object<string, string|true>} [attrs] Extra attributes on the root.
 */

const VARIANTS = ["subtle", "ghost", "outline"];
const THEMES = ["gray", "red"];

/**
 * A list of rows (boxed, or flat inside a pane), each with an optional avatar or icon, a title and subtitle, a meta
 * text, a badge, always-visible controls and hover actions. Rows are links when they have an href. With `max`, the
 * list folds to that many rows and a footer button reveals the rest, for good.
 * With `groups`, the rows sit under a heading per group (a boxed list boxes each group).
 * One row can be marked selected (`aria-current` and `data-selected`) for master-detail
 * layouts: the caller owns the state through `selected`, `set_selected(id)` and `get_selected()`.
 * Styles are in espresso/components/list.css.
 *
 * @example
 * const list = new frappe.ui.List({
 *   items: [
 *     { id: "john", title: "John Doe", subtitle: "Referred by Jane", meta: "6d ago",
 *       avatar: { label: "John Doe" }, href: "/desk/job-applicant/john",
 *       actions: [{ label: __("Shortlist"), onclick: (item, list) => shortlist(item).then(() => list.remove_item(item.id)) }] },
 *   ],
 *   max: 5,
 *   empty: { title: __("No applicants") },
 * });
 * wrapper.append(list.$el);
 */
frappe.ui.List = class List {
	/** @param {ListOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.$el = $(`<div ${safe_attrs(opts.attrs, "List").join(" ")}></div>`);
		this.el = this.$el[0];
		this.el.className = ["es-list", opts.css_class].filter(Boolean).join(" ");
		if (opts.variant === "flat") this.el.dataset.variant = "flat";

		this.is_expanded = false;
		this.selected = opts.selected ?? null;
		this.groups = opts.groups || null;
		this.$el.data("es-list", this);
		this.set_items(opts.items || []);
	}

	/** Replace all items, and the groups when given, and rebuild the rows. */
	set_items(items, groups = this.groups) {
		this.items = items.slice();
		this.groups = groups || null;
		this.render();
	}

	/** Merge new properties into an item and re-render its row. */
	update_item(item_id, changes) {
		const item = this.get_item(item_id);
		if (!item) return;
		Object.assign(item, changes);
		const row = this.rows.get(item_id);
		if (row) row.replaceWith(this.make_row(item));
	}

	remove_item(item_id) {
		const index = this.items.findIndex((item) => item.id === item_id);
		if (index === -1) return;
		this.items.splice(index, 1);
		this.render();
	}

	get_item(item_id) {
		return this.items.find((item) => item.id === item_id);
	}

	get_items() {
		return this.items;
	}

	get_selected() {
		return this.selected;
	}

	/** Highlight a row; pass null to clear. Pass `scroll: true` to bring it into view. */
	set_selected(item_id, { scroll = false } = {}) {
		const previous = this.rows.get(this.selected);
		this.selected = item_id ?? null;
		if (previous) this.mark_selected(previous, false);
		const row = this.rows.get(this.selected);
		if (!row) return;
		this.mark_selected(row, true);
		if (scroll) row.scrollIntoView({ block: "nearest" });
	}

	mark_selected(row, is_selected) {
		row.toggleAttribute("data-selected", is_selected);
		if (is_selected) row.setAttribute("aria-current", "true");
		else row.removeAttribute("aria-current");
	}

	render() {
		const max = this.opts.max;
		const is_folded = Boolean(max) && !this.is_expanded && this.items.length > max;
		const shown = is_folded ? this.items.slice(0, max) : this.items;

		if (!this.get_item(this.selected)) this.selected = null;
		this.rows = new Map();
		const children = this.groups
			? this.make_groups(shown)
			: shown.map((item) => this.make_row(item));
		if (is_folded) children.push(this.make_more(this.items.length));
		if (!this.items.length && this.opts.empty) {
			children.push(frappe.ui.empty_state(this.opts.empty)[0]);
		}
		this.el.toggleAttribute("data-empty", !this.items.length);
		this.el.toggleAttribute("data-grouped", Boolean(this.groups));
		this.el.replaceChildren(...children);
	}

	/** A heading and a box of rows for each group that has rows. */
	make_groups(items) {
		return this.groups.flatMap(({ id, label, count }) => {
			const rows = items
				.filter((item) => item.group === id)
				.map((item) => this.make_row(item));
			if (!rows.length) return [];
			const head = document.createElement("div");
			head.className = "es-list__group-head";
			head.append(this.make_part("span", "es-list__group-label text-p-sm-medium", label));
			if (count != null) {
				head.append(this.make_part("span", "es-list__group-count text-p-sm", count));
			}
			const group = document.createElement("div");
			group.className = "es-list__group";
			group.append(...rows);
			return [head, group];
		});
	}

	make_row(item) {
		const href = safe_href(item.href, "list");
		const has_actions = Boolean(item.actions?.length);
		const row = document.createElement(href ? "a" : "div");
		row.className = "es-list__row";
		row.dataset.id = item.id;
		if (href) {
			row.href = href;
		} else if (this.opts.on_click) {
			row.setAttribute("role", "button");
		}
		// a row with only actions still needs focus, or the keyboard can't reveal them
		if (!href && (this.opts.on_click || has_actions)) row.tabIndex = 0;
		row.toggleAttribute("data-has-actions", has_actions);
		if (item.id === this.selected) this.mark_selected(row, true);

		const lead = this.make_lead(item);
		if (lead) row.append(lead);
		row.toggleAttribute("data-avatar", Boolean(item.avatar));
		row.append(this.make_text(item));
		// badge before meta, so the meta lines up in one column down the list
		if (item.badge) row.insertAdjacentHTML("beforeend", this.make_badge_html(item.badge));
		if (item.meta) row.append(this.make_part("span", "es-list__meta", item.meta));
		const controls = this.make_controls(item, Boolean(href));
		if (controls) row.append(controls);
		if (has_actions) row.append(this.make_actions(item, Boolean(href)));

		row.addEventListener("click", (event) => this.handle_click(item, event));
		row.addEventListener("keydown", (event) => this.handle_keydown(item, event));
		this.rows.set(item.id, row);
		return row;
	}

	make_part(tag, class_name, text) {
		const part = document.createElement(tag);
		part.className = class_name;
		part.textContent = text;
		return part;
	}

	make_lead(item) {
		if (!item.avatar && !item.icon) return null;
		const lead = document.createElement("span");
		lead.className = "es-list__lead";
		if (item.avatar) {
			lead.append(
				frappe.ui.avatar({
					label: item.avatar.label,
					image: item.avatar.image,
					size: "md",
					theme: "auto",
				})[0]
			);
		} else {
			lead.insertAdjacentHTML("beforeend", icon_html(item.icon, "", "List"));
		}
		return lead;
	}

	make_text(item) {
		const text = document.createElement("span");
		text.className = "es-list__text";
		text.append(this.make_part("span", "es-list__title", item.title));
		if (item.subtitle) {
			text.append(this.make_part("span", "es-list__subtitle", item.subtitle));
		}
		return text;
	}

	make_badge_html(badge) {
		return frappe.ui.badge.html({
			label: badge.label,
			theme: badge.theme,
			size: "sm",
			css_class: "es-list__badge",
		});
	}

	make_controls(item, is_link) {
		if (!item.controls) return null;
		const content = [item.controls(item, this)].flat().filter(Boolean);
		if (!content.length) return null;
		const controls = document.createElement("span");
		controls.className = "es-list__controls";
		for (const node of content) controls.append(...(node.jquery ? node.get() : [node]));
		this.contain_clicks(controls, is_link);
		return controls;
	}

	/**
	 * Keeps clicks inside controls and actions from opening the row or following its link, including clicks
	 * that land on the container (a busy button ignores pointer events). Keys need no stop: handle_keydown
	 * ignores keys pressed on anything but the row itself.
	 */
	contain_clicks(element, is_link) {
		const contain = (event) => {
			event.stopPropagation();
			if (is_link && !event.target.closest("input, select, textarea"))
				event.preventDefault();
		};
		element.addEventListener("click", contain);
		element.addEventListener("auxclick", contain);
	}

	make_actions(item, is_link) {
		const actions = document.createElement("span");
		actions.className = "es-list__actions";
		this.contain_clicks(actions, is_link);
		for (const action of item.actions) {
			const $button = frappe.ui.button({
				label: action.label,
				variant: validated(action.variant, VARIANTS, "action variant", "List"),
				theme: validated(action.theme, THEMES, "action theme", "List"),
				size: "sm",
				onclick: () => action.onclick?.(item, this),
			});
			actions.append($button[0]);
		}
		return actions;
	}

	make_more(count) {
		const button = document.createElement("button");
		button.type = "button";
		button.className = "es-list__more";
		button.textContent = (this.opts.more_label || __("Show all {0}")).replace("{0}", count);
		button.addEventListener("click", () => {
			this.is_expanded = true;
			this.render();
		});
		return button;
	}

	handle_click(item, event) {
		if (!this.opts.on_click) return;
		const is_modified = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
		if (item.href && (is_modified || event.button !== 0)) return;
		this.opts.on_click(item, this, event);
		// desk's router follows every link click, even a prevented one
		if (event.defaultPrevented) event.stopPropagation();
	}

	handle_keydown(item, event) {
		// keys pressed on an action button belong to the button
		if (event.target !== event.currentTarget || item.href || !this.opts.on_click) return;
		if (event.key === "Enter" || event.key === " ") {
			event.preventDefault();
			this.opts.on_click(item, this, event);
		}
	}
};

/**
 * Returns the element; the instance is on `.data("es-list")`.
 * @param {ListOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.list = (opts) => new frappe.ui.List(opts).$el;

export default frappe.ui.list;
