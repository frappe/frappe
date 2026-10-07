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
 * @property {"pending"|"done"|"skipped"} [status="pending"]
 * @property {string} [description] Plain text shown as the label's tooltip.
 * @property {string} [value] Muted second line, e.g. a default or a linked record name.
 * @property {string} [assignee] User ID of the person who owns the item.
 * @property {string} [due_date] Date the item is due, as YYYY-MM-DD. Past and unfinished shows as overdue.
 * @property {ChecklistAction[]} [actions] Buttons at the end of the row.
 * @property {boolean} [skippable] Shows a Skip button while the item is pending.
 * @property {boolean} [optional] Shows an Optional badge and leaves the item out of progress, unless every item is optional.
 * @property {string} [locked] Why the item can't be done yet. Replaces the second line and disables the actions; Skip stays available.
 *
 * @typedef {Object} ChecklistOpts
 * @property {string} title Translated text in the card's head.
 * @property {ChecklistItem[]} items
 * @property {(item:ChecklistItem, checklist:Checklist)=>void|Promise} [on_skip] Runs before an item is marked skipped; reject to keep it pending.
 * @property {(item:ChecklistItem, user:string|null)=>void|Promise} [on_assign] Makes the assignee editable; runs before the item changes, reject to keep the old one.
 * @property {(item:ChecklistItem, date:string|null)=>void|Promise} [on_due_date_change] Makes the due date editable, the same way.
 * @property {string} [css_class] Extra classes on the root.
 */

const STATUSES = ["pending", "done", "skipped"];

/**
 * A checklist card: a title, progress, and one row per item with its owner, due date and
 * actions. The card folds away to its head and progress. The caller owns completion: an
 * item only changes status through set_status or update_item, so a row is checked when its
 * record exists, not when someone ticks it.
 * Styles are in espresso/components/checklist.css.
 *
 * @example
 * const checklist = new frappe.ui.Checklist({
 *   title: __("Onboarding"),
 *   items: [
 *     { id: "create_user", label: __("Create User"), assignee: "hr@example.com", due_date: "2026-10-12",
 *       actions: [{ label: __("Create"), onclick: (item, list) => create_user().then(() => list.set_status(item.id, "done")) }] },
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
				<span class="es-checklist__heading">
					<span class="es-checklist__name"></span>
					<span class="es-checklist__count"></span>
				</span>
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
			done: counted.filter((item) => item.status === "done").length,
			skipped: counted.filter((item) => item.status === "skipped").length,
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
		row.setAttribute("data-status", item.status || "pending");
		row.toggleAttribute("data-locked", Boolean(reason));
		row.toggleAttribute("data-overdue", this.is_overdue(item));
		row.querySelector(".es-checklist__marker").innerHTML = this.get_marker_icon(item, reason);

		const meta = [reason || item.value, item.status === "skipped" && __("Skipped")];
		row.querySelector(".es-checklist__meta").textContent = meta.filter(Boolean).join(", ");

		row.querySelector(".es-checklist__owner").replaceChildren(this.make_owner(item));
		row.querySelector(".es-checklist__due").replaceChildren(this.make_due(item));
		row.querySelector(".es-checklist__actions").replaceChildren(
			...this.make_actions(item, Boolean(reason))
		);
	}

	get_marker_icon(item, locked) {
		const name =
			item.status === "done"
				? "circle-check"
				: item.status === "skipped"
				? "circle-dashed"
				: locked
				? "lock"
				: "circle";
		return frappe.utils.icon(name, "sm", "", "", "", true);
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

		const trigger = this.make_trigger(face, user ? user.fullname : __("Assign"));
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

		const trigger = this.make_trigger($("<span></span>").text(text), __("Due date"));
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
		if (item.skippable && (item.status || "pending") === "pending") {
			buttons.push(
				frappe.ui.button({
					label: __("Skip"),
					variant: "ghost",
					onclick: () => this.skip(item),
				})
			);
		}
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

	skip(item) {
		return Promise.resolve(this.opts.on_skip?.(item, this)).then(() =>
			this.set_status(item.id, "skipped")
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
		return item.status === "done" || item.status === "skipped";
	}
};

/**
 * Returns the element; the instance is on `.data("es-checklist")`.
 * @param {ChecklistOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.checklist = (opts) => new frappe.ui.Checklist(opts).$el;

export default frappe.ui.checklist;
