import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ChecklistAction
 * Button options for frappe.ui.button. `onclick` gets the item and the checklist.
 * Actions default to the subtle variant and follow the Skip button.
 *
 * @typedef {Object} ChecklistItem
 * @property {string} id Unique across the whole checklist.
 * @property {string} label Translated text. Rendered as text, never HTML.
 * @property {boolean} [done] The work is finished; the row is checked.
 * @property {boolean} [skipped] Set aside without doing it; counts toward progress but not as done.
 * @property {"in_progress"|"stuck"} [status] Where unfinished work stands, shown as a badge. Ignored once done or skipped.
 * @property {string} [description] Plain text shown as the label's tooltip.
 * @property {string} [value] Muted second line, e.g. a default or a linked record name.
 * @property {string} [assignee] User ID of the person who owns the item.
 * @property {string} [due_date] Date the item is due, as YYYY-MM-DD. Past and unfinished shows as overdue.
 * @property {ChecklistAction[]} [actions] Buttons at the end of the row.
 * @property {boolean} [skippable] Offers Skip, and Undo skip once skipped, in the row's ... menu.
 * @property {boolean} [optional] Shows an Optional badge and leaves the item out of progress, unless every item is optional.
 * @property {string} [locked] Why the item can't be done yet. Shown on the lock icon's tooltip; the actions are disabled, Skip stays available.
 *
 * @typedef {Object} ChecklistOpts
 * @property {string} title Translated text in the card's head.
 * @property {ChecklistItem[]} items
 * @property {(item:ChecklistItem, checklist:Checklist)=>void|Promise} [on_skip] Runs before an item is marked skipped; reject to keep it pending.
 * @property {(item:ChecklistItem, checklist:Checklist)=>void|Promise} [on_unskip] Runs before a skip is undone; reject to keep it skipped.
 * @property {(item:ChecklistItem, user:string|null)=>void|Promise} [on_assign] Makes the assignee editable; runs before the item changes, reject to keep the old one.
 * @property {(item:ChecklistItem, date:string|null)=>void|Promise} [on_due_date_change] Makes the due date editable, the same way.
 * @property {(item:ChecklistItem, status:string|null)=>void|Promise} [on_status_change] Makes an unfinished item's marker a menu to set it In Progress or Stuck, or clear that; finishing stays with the caller.
 * @property {string} [css_class] Extra classes on the root.
 */

const STATUSES = ["in_progress", "stuck"];

const STATUS_LABELS = {
	in_progress: __("In Progress"),
	stuck: __("Stuck"),
};

const MARKER_ICONS = {
	pending: "circle",
	in_progress: "circle-dot-dashed",
	stuck: "circle-alert",
	done: "circle-check",
	skipped: "circle-dashed",
};

/**
 * A checklist card: a title, progress, and one row per item with its owner, due date and
 * actions. The card folds away to its head and progress. The caller owns completion: an
 * item is only checked through update_item({ done: true }), so a row is checked when its
 * record exists, not when someone ticks it.
 * Styles are in espresso/components/checklist.css.
 *
 * @example
 * const checklist = new frappe.ui.Checklist({
 *   title: __("Onboarding"),
 *   items: [
 *     { id: "create_user", label: __("Create User"), assignee: "hr@example.com", due_date: "2026-10-12",
 *       actions: [{ label: __("Create"), onclick: (item, list) => create_user().then(() => list.update_item(item.id, { done: true })) }] },
 *   ],
 *   on_assign: (item, user) => save_assignee(item.id, user),
 *   on_due_date_change: (item, date) => save_due_date(item.id, date),
 * });
 * wrapper.append(checklist.$el);
 */
frappe.ui.Checklist = class Checklist {
	/** @param {ChecklistOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.el = document.createElement("section");
		this.el.className = ["es-checklist", opts.css_class].filter(Boolean).join(" ");
		this.el.innerHTML = `
			<button type="button" class="es-checklist__head">
				<span class="es-checklist__name"></span>
				<span class="es-checklist__count"></span>
				${frappe.utils.icon("chevron-down", "sm", "", "", "es-checklist__chevron", true)}
			</button>
			<div class="es-checklist__progress"></div>
			<div class="es-checklist__collapse"><div class="es-checklist__items"></div></div>`;
		this.head = this.el.querySelector(".es-checklist__head");
		this.list = this.el.querySelector(".es-checklist__items");
		this.el.querySelector(".es-checklist__name").textContent = opts.title || "";
		this.head.addEventListener("click", () => this.set_expanded(!this.is_expanded()));
		this.head.setAttribute("aria-expanded", "true");

		this.$el = $(this.el);
		this.$el.data("es-checklist", this);
		this.set_items(opts.items || []);
	}

	/** Replace all items and rebuild the rows. */
	set_items(items) {
		this.items = new Map(items.map((item) => [item.id, item]));
		this.rows = new Map();
		this.list.replaceChildren(...items.map((item) => this.make_row(item)));
		this.make_progress();
		this.update_head();
		items.forEach((item) => this.update_row(item));
	}

	/** Set an item In Progress or Stuck, or clear that with null. */
	set_status(item_id, status) {
		this.update_item(item_id, { status: validated(status, STATUSES, "status", "Checklist") });
	}

	/** Merge new properties into an item and re-render its row. */
	update_item(item_id, changes) {
		const item = this.items.get(item_id);
		if (!item) return;
		Object.assign(item, changes);
		this.update_row(item);
		this.update_head();
	}

	get_item(item_id) {
		return this.items.get(item_id);
	}

	get_progress() {
		const items = [...this.items.values()];
		const required = items.filter((item) => !item.optional);
		const counted = required.length ? required : items;
		return {
			total: counted.length,
			done: counted.filter((item) => item.done).length,
			skipped: counted.filter((item) => !item.done && item.skipped).length,
		};
	}

	is_expanded() {
		return !this.el.hasAttribute("data-collapsed");
	}

	set_expanded(expanded) {
		this.el.toggleAttribute("data-collapsed", !expanded);
		this.head.setAttribute("aria-expanded", String(expanded));
	}

	make_progress() {
		const { total } = this.get_progress();
		this.progress = total
			? new frappe.ui.Progress({ intervals: true, interval_count: total, size: "md" })
			: null;
		this.el
			.querySelector(".es-checklist__progress")
			.replaceChildren(...(this.progress ? [this.progress.el] : []));
	}

	update_head() {
		const { total, done, skipped } = this.get_progress();
		this.el.querySelector(".es-checklist__count").textContent = skipped
			? __("{0} of {1} done, {2} skipped", [done, total, skipped])
			: __("{0} of {1} done", [done, total]);
		this.progress?.set_value(total ? ((done + skipped) / total) * 100 : 0);
	}

	make_row(item) {
		const row = document.createElement("div");
		row.className = "es-checklist__item";
		row.innerHTML = `
			<span class="es-checklist__marker"></span>
			<div class="es-checklist__text">
				<div class="es-checklist__title"><span class="es-checklist__label"></span></div>
				<div class="es-checklist__meta"></div>
			</div>
			<div class="es-checklist__status"></div>
			<div class="es-checklist__owner"></div>
			<div class="es-checklist__due"></div>
			<div class="es-checklist__actions"></div>`;
		const label = row.querySelector(".es-checklist__label");
		label.textContent = item.label;
		if (item.description) label.title = item.description;
		if (item.optional) {
			label.insertAdjacentHTML(
				"afterend",
				frappe.ui.badge.html({ label: __("Optional"), size: "sm" })
			);
		}
		this.rows.set(item, row);
		return row;
	}

	update_row(item) {
		const row = this.rows.get(item);
		const reason = this.is_finished(item) ? null : item.locked;
		row.setAttribute("data-status", this.get_state(item));
		row.toggleAttribute("data-locked", Boolean(reason));
		row.toggleAttribute("data-overdue", this.is_overdue(item));
		row.querySelector(".es-checklist__marker").replaceChildren(this.make_marker(item, reason));

		row.querySelector(".es-checklist__meta").textContent = item.value || "";
		row.querySelector(".es-checklist__status").replaceChildren(this.make_status(item));

		row.querySelector(".es-checklist__owner").replaceChildren(this.make_owner(item));
		row.querySelector(".es-checklist__due").replaceChildren(this.make_due(item));
		row.querySelector(".es-checklist__actions").replaceChildren(
			...this.make_actions(item, Boolean(reason))
		);
	}

	make_marker(item, reason) {
		if (reason) return this.make_lock(reason);

		const icon = $(
			frappe.utils.icon(MARKER_ICONS[this.get_state(item)], "sm", "", "", "", true)
		);
		if (!this.opts.on_status_change || this.is_finished(item)) return icon[0];

		const trigger = this.make_trigger(icon, __("Set status"));
		const set = (status) =>
			Promise.resolve(this.opts.on_status_change(item, status)).then(() =>
				this.update_item(item.id, { status })
			);
		const options = STATUSES.filter((status) => status !== item.status).map((status) => ({
			label: STATUS_LABELS[status],
			icon: MARKER_ICONS[status],
			onclick: () => set(status),
		}));
		if (item.status) {
			options.push({ label: __("Clear status"), icon: "circle", onclick: () => set(null) });
		}
		new frappe.ui.Dropdown({ trigger, options });
		return trigger;
	}

	// The lock says what the row is waiting for, on hover and on focus.
	make_lock(reason) {
		const lock = document.createElement("span");
		lock.className = "es-checklist__lock";
		lock.tabIndex = 0;
		lock.setAttribute("role", "img");
		lock.setAttribute("aria-label", reason);
		lock.innerHTML = frappe.utils.icon("lock", "sm", "", "", "", true);
		frappe.ui.tooltip(lock, { text: reason });
		return lock;
	}

	make_status(item) {
		const label = !this.is_finished(item) && STATUS_LABELS[item.status];
		if (!label) return document.createTextNode("");
		return frappe.ui.badge({
			label,
			theme: item.status === "stuck" ? "red" : "gray",
			size: "sm",
		})[0];
	}

	make_owner(item) {
		const user = item.assignee && frappe.user_info(item.assignee);
		const face = user
			? frappe.ui.avatar({
					label: user.fullname,
					image: user.image,
					size: "sm",
					theme: "auto",
			  })
			: $(frappe.utils.icon("user-plus", "sm", "", "", "", true));
		if (!this.opts.on_assign) return user ? face[0] : document.createTextNode("");

		const trigger = this.make_control(face, user ? user.fullname : __("Assign"));
		trigger.setAttribute("data-icon-button", "true");
		this.attach_editor(trigger, item, {
			fieldtype: "Link",
			options: "User",
			label: __("Assigned To"),
			value: item.assignee,
			save: (value) => this.opts.on_assign(item, value),
			field: "assignee",
		});
		return trigger;
	}

	make_due(item) {
		const text = item.due_date
			? frappe.datetime.str_to_user(item.due_date)
			: this.opts.on_due_date_change
			? __("Set date")
			: "";
		if (!this.opts.on_due_date_change) return document.createTextNode(text);

		const trigger = this.make_control($("<span></span>").text(text), __("Due date"));
		trigger.toggleAttribute("data-empty", !item.due_date);
		this.attach_editor(trigger, item, {
			fieldtype: "Date",
			label: __("Due Date"),
			value: item.due_date,
			save: (value) => this.opts.on_due_date_change(item, value),
			field: "due_date",
		});
		return trigger;
	}

	make_trigger($content, label) {
		const trigger = document.createElement("button");
		trigger.type = "button";
		trigger.className = "es-checklist__trigger";
		trigger.setAttribute("aria-label", label);
		trigger.title = label;
		trigger.append(...$content.toArray());
		return trigger;
	}

	// Owner and date: ghost buttons, so they read as clickable.
	make_control($content, label) {
		const control = document.createElement("button");
		control.className = "es-checklist__control";
		frappe.ui.button.dress(control, { variant: "ghost" });
		control.setAttribute("aria-label", label);
		control.append(...$content.toArray());
		frappe.ui.tooltip(control, { text: label });
		return control;
	}

	// One field in a popover; a change saves through the caller, then updates the row.
	attach_editor(trigger, item, editor) {
		const popover = new frappe.ui.Popover({
			trigger,
			align: "end",
			content: () => {
				const body = document.createElement("div");
				body.className = "es-checklist__editor";
				const control = frappe.ui.form.make_control({
					parent: body,
					df: {
						fieldtype: editor.fieldtype,
						options: editor.options,
						label: editor.label,
						fieldname: editor.field,
						onchange: () => {
							const value = control.get_value() || null;
							if (value === (editor.value || null)) return;
							Promise.resolve(editor.save(value)).then(() => {
								popover.close();
								this.update_item(item.id, { [editor.field]: value });
							});
						},
					},
					render_input: true,
				});
				control.set_value(editor.value || "");
				return body;
			},
		});
	}

	make_actions(item, locked) {
		const buttons = [];
		if (item.skippable && !item.done) buttons.push(this.make_menu(item));
		for (const action of item.actions || []) {
			buttons.push(
				frappe.ui.button({
					...action,
					size: action.size || "sm",
					variant: action.variant || "subtle",
					disabled: locked || action.disabled,
					onclick: () => action.onclick?.(item, this),
				})
			);
		}
		return buttons.map(($button) => $button[0]);
	}

	// Skip sits behind a click, so it isn't hit by accident; a skip can be undone.
	make_menu(item) {
		const $button = frappe.ui.button({
			variant: "ghost",
			icon: "ellipsis",
			tooltip: __("More actions"),
			css_class: "es-checklist__menu",
		});
		new frappe.ui.Dropdown({
			trigger: $button,
			align: "end",
			options: () =>
				item.skipped
					? [{ label: __("Undo skip"), onclick: () => this.unskip(item) }]
					: [{ label: __("Skip"), onclick: () => this.skip(item) }],
		});
		return $button;
	}

	skip(item) {
		return Promise.resolve(this.opts.on_skip?.(item, this)).then(() =>
			this.update_item(item.id, { skipped: true })
		);
	}

	unskip(item) {
		return Promise.resolve(this.opts.on_unskip?.(item, this)).then(() =>
			this.update_item(item.id, { skipped: false })
		);
	}

	is_overdue(item) {
		return Boolean(
			item.due_date &&
				!this.is_finished(item) &&
				frappe.datetime.get_diff(item.due_date, frappe.datetime.get_today()) < 0
		);
	}

	is_finished(item) {
		return Boolean(item.done || item.skipped);
	}

	/** One word for the marker and data-status: done, skipped, stuck, in_progress or pending. */
	get_state(item) {
		if (item.done) return "done";
		if (item.skipped) return "skipped";
		return item.status || "pending";
	}
};

/**
 * Returns the element; the instance is on `.data("es-checklist")`.
 * @param {ChecklistOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.checklist = (opts) => new frappe.ui.Checklist(opts).$el;

export default frappe.ui.checklist;
