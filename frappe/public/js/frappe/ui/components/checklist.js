import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ChecklistAction
 * Button options for frappe.ui.button. `onclick` gets the item and the checklist.
 * The first action is solid with an arrow, the rest are subtle; icons of their own are dropped,
 * so every row's buttons look alike.
 *
 * @typedef {Object} ChecklistItem
 * @property {string} id Unique across the whole checklist.
 * @property {string} label Translated text. Rendered as text, never HTML.
 * @property {boolean} [done] The work is finished; the row is checked.
 * @property {boolean} [skipped] Set aside without doing it; counts toward progress but not as done.
 * @property {"in_progress"|"stuck"} [status] Where unfinished work stands, shown as a badge. Ignored once done or skipped.
 * @property {string} [description] Plain text shown when the row is open.
 * @property {string} [value] Muted second line, e.g. a default or a linked record name.
 * @property {string} [assignee] User ID of the person who owns the item.
 * @property {string} [due_date] Date the item is due, as YYYY-MM-DD. Past and unfinished shows as overdue.
 * @property {ChecklistAction[]} [actions] Buttons in the open row.
 * @property {boolean} [skippable] Offers Skip, and Undo skip once skipped, in the open row.
 * @property {boolean} [optional] Shows an Optional badge and leaves the item out of progress, unless every item is optional.
 * @property {string} [locked] Why the item can't be done yet. Shown on the lock icon's tooltip and in the open row; the actions are disabled, Skip stays available.
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
 * A checklist card, drawn like the workspace onboarding: a title, progress, and one row per
 * item with its owner and due date. One row is open at a time and shows the item's description
 * and actions; the first unfinished row opens first, and finishing the open row opens the next.
 * The card folds away to its head and progress. The caller owns completion: an item is only
 * checked through update_item({ done: true }), so a row is checked when its record exists, not
 * when someone ticks it.
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

		this.items = new Map();
		this.rows = new Map();
		this.open_id = null;
		this.closed_by_user = false;

		this.$el = $(this.el);
		this.$el.data("es-checklist", this);
		this.set_items(opts.items || []);
	}

	/** Replace all items. Rows are kept by id, so the open row stays open across a refresh. */
	set_items(items) {
		this.items = new Map(items.map((item) => [item.id, item]));
		this.rows = new Map(
			items.map((item) => [item.id, this.rows.get(item.id) || this.make_row(item.id)])
		);
		this.list.replaceChildren(...this.rows.values());
		this.make_progress();
		this.update_head();
		items.forEach((item) => this.update_row(item));
		this.sync_open();
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
		this.sync_open();
	}

	get_item(item_id) {
		return this.items.get(item_id);
	}

	/** Open one row and close the others; null closes them all. */
	set_open(item_id) {
		const item = this.items.get(item_id);
		this.open_id = item && this.has_body(item) ? item_id : null;
		this.open_was_finished = Boolean(item && this.is_finished(item));
		this.closed_by_user = !this.open_id;
		this.update_open();
	}

	get_open() {
		return this.items.get(this.open_id) || null;
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

	// Rebuilt only when the count changes, so the bar animates from one value to the next.
	make_progress() {
		const { total } = this.get_progress();
		if (this.progress && this.progress_total === total) return;
		this.progress_total = total;
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

	// The open row stays open until it finishes; then the next unfinished row opens. A row the
	// user opened while finished stays open, and a user who closed every row keeps them closed.
	sync_open() {
		const open = this.items.get(this.open_id);
		let next = open;
		if (open && !this.open_was_finished && this.is_finished(open)) {
			next = this.get_next(open);
		} else if (!open && !this.closed_by_user) {
			next = this.get_next();
		}
		this.open_id = next && this.has_body(next) ? next.id : null;
		this.open_was_finished = Boolean(next && this.is_finished(next));
		this.update_open();
	}

	get_next(after) {
		const items = [...this.items.values()];
		const start = after ? items.indexOf(after) + 1 : 0;
		return [...items.slice(start), ...items.slice(0, start)].find(
			(item) => !this.is_finished(item) && this.has_body(item)
		);
	}

	update_open() {
		for (const [id, row] of this.rows) {
			const is_open = id === this.open_id;
			row.toggleAttribute("data-open", is_open);
			row.querySelector(".es-checklist__toggle").setAttribute(
				"aria-expanded",
				String(is_open)
			);
			row.querySelector(".es-checklist__drawer").inert = !is_open;
		}
	}

	make_row(id) {
		const row = document.createElement("div");
		row.className = "es-checklist__item";
		row.innerHTML = `
			<div class="es-checklist__row">
				<span class="es-checklist__marker"></span>
				<button type="button" class="es-checklist__toggle">
					<span class="es-checklist__title"><span class="es-checklist__label"></span></span>
					<span class="es-checklist__meta"></span>
				</button>
				<div class="es-checklist__status"></div>
				<div class="es-checklist__owner"></div>
				<div class="es-checklist__due"></div>
			</div>
			<div class="es-checklist__drawer">
				<div class="es-checklist__body">
					<div class="es-checklist__content">
						<div class="es-checklist__description"></div>
						<div class="es-checklist__note"></div>
						<div class="es-checklist__actions"></div>
					</div>
				</div>
			</div>`;

		// The whole head takes the click, not only the toggle inside its padding; the toggle
		// keeps it reachable from the keyboard, and its click bubbles up to here.
		const controls = ".es-checklist__marker, .es-checklist__owner, .es-checklist__due";
		row.querySelector(".es-checklist__row").addEventListener("click", (e) => {
			if (e.target.closest(controls) || row.hasAttribute("data-empty")) return;
			this.set_open(this.open_id === id ? null : id);
		});
		return row;
	}

	update_row(item) {
		const row = this.rows.get(item.id);
		const reason = this.is_finished(item) ? null : item.locked;
		row.setAttribute("data-status", this.get_state(item));
		row.toggleAttribute("data-locked", Boolean(reason));
		row.toggleAttribute("data-overdue", this.is_overdue(item));
		row.toggleAttribute("data-empty", !this.has_body(item));
		row.querySelector(".es-checklist__marker").replaceChildren(this.make_marker(item, reason));
		row.querySelector(".es-checklist__title").replaceChildren(...this.make_title(item));
		row.querySelector(".es-checklist__meta").textContent = item.value || "";
		row.querySelector(".es-checklist__status").replaceChildren(this.make_status(item));
		row.querySelector(".es-checklist__owner").replaceChildren(this.make_owner(item));
		row.querySelector(".es-checklist__due").replaceChildren(this.make_due(item));

		row.querySelector(".es-checklist__description").textContent = item.description || "";
		row.querySelector(".es-checklist__note").textContent = reason || "";
		row.querySelector(".es-checklist__actions").replaceChildren(
			...this.make_actions(item, Boolean(reason))
		);
	}

	make_title(item) {
		const label = document.createElement("span");
		label.className = "es-checklist__label";
		label.textContent = item.label;
		if (!item.optional) return [label];
		return [label, frappe.ui.badge({ label: __("Optional"), size: "sm" })[0]];
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
		if (item.skipped && !item.done) {
			const skipped = document.createElement("span");
			skipped.className = "es-checklist__skipped";
			skipped.textContent = __("Skipped");
			return skipped;
		}
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
		this.attach_user_picker(trigger, item);
		return trigger;
	}

	// The list view's searchable dropdown: the users Assign To offers, filtered by
	// frappe.utils.setup_search as the user types.
	attach_user_picker(trigger, item) {
		const assign = (user) => {
			popover.close();
			this.save_field(item, "assignee", user, this.opts.on_assign);
		};
		const popover = new frappe.ui.Popover({
			trigger,
			align: "end",
			css_class: "es-checklist__picker",
			content: () => {
				const picker = document.createElement("div");
				picker.innerHTML = `
					<input type="text" data-element="search" class="form-control es-checklist__search">
					<div class="es-checklist__options"></div>`;
				picker.querySelector("input").placeholder = __("Search");
				return picker;
			},
			on_open: () =>
				this.get_users().then((users) => {
					const $picker = $(popover.panel);
					$picker
						.find(".es-checklist__options")
						.empty()
						.append(this.make_user_options(users, item, assign));
					frappe.utils.setup_search(
						$picker,
						".es-checklist__option:not([data-unassign])",
						".es-checklist__option-label",
						"data-name"
					);
				}),
		});
	}

	get_users() {
		this.users ??= frappe.db.get_link_options("User", "", {
			user_type: "System User",
			enabled: 1,
		});
		return this.users;
	}

	make_user_options(users, item, assign) {
		const rows = users.map(({ value, description }) => {
			const name = description || value;
			const row = this.make_option(name, description ? value : "", () => assign(value));
			row.querySelector(".es-checklist__option-label").setAttribute("data-name", value);
			row.prepend(
				frappe.ui.avatar({
					label: name,
					image: frappe.user_info(value).image,
					size: "sm",
					theme: "auto",
				})[0]
			);
			row.toggleAttribute("data-selected", value === item.assignee);
			return row;
		});
		if (item.assignee) {
			const unassign = this.make_option(__("Unassign"), "", () => assign(null));
			unassign.prepend($(frappe.utils.icon("user-x", "sm", "", "", "", true))[0]);
			unassign.setAttribute("data-unassign", "");
			rows.push(unassign);
		}
		return rows;
	}

	make_option(label, description, onclick) {
		const row = document.createElement("button");
		row.type = "button";
		row.className = "es-checklist__option";
		row.innerHTML = `<span class="es-checklist__option-text">
			<span class="es-checklist__option-label"></span>
			<span class="es-checklist__option-description"></span>
		</span>`;
		row.querySelector(".es-checklist__option-label").textContent = label;
		row.querySelector(".es-checklist__option-description").textContent = description;
		row.addEventListener("click", onclick);
		return row;
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
		this.attach_date_picker(trigger, item);
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

	// The calendar alone in a popover: picking a day saves it, Clear removes it.
	attach_date_picker(trigger, item) {
		const popover = new frappe.ui.Popover({
			trigger,
			align: "end",
			css_class: "es-checklist__calendar",
			content: () => {
				const calendar = document.createElement("div");
				const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
				const lang = frappe.boot.user?.language;
				const due = item.due_date && frappe.datetime.str_to_obj(item.due_date);
				let ready = false;
				const picker = $(calendar)
					.datepicker({
						language: $.fn.datepicker.language[lang] ? lang : "en",
						firstDay: frappe.datetime.get_first_day_of_the_week_index(),
						todayButton: today,
						clearButton: Boolean(due),
						startDate: due || today,
						onSelect: (_, date) => {
							if (!ready) return;
							const value = date ? frappe.datetime.obj_to_str(date) : null;
							popover.close();
							this.save_field(item, "due_date", value, this.opts.on_due_date_change);
						},
					})
					.data("datepicker");
				if (due) picker.selectDate(due);
				ready = true;
				$(calendar).find('[data-action="today"]').text(__("Today"));
				$(calendar).find('[data-action="clear"]').text(__("Clear"));
				return calendar;
			},
		});
	}

	// Saves through the caller, then updates the row; a rejected save leaves the row as it was.
	save_field(item, field, value, save) {
		if (value === (item[field] || null)) return;
		return Promise.resolve(save(item, value)).then(() =>
			this.update_item(item.id, { [field]: value })
		);
	}

	// A skipped row offers only Undo skip, so skipping can't stand in for unlocking it.
	make_actions(item, locked) {
		if (item.skipped && !item.done) {
			return item.skippable
				? [this.make_button(__("Undo skip"), () => this.unskip(item))]
				: [];
		}
		const buttons = (item.actions || []).map(
			({ icon, icon_left, icon_right, ...action }, index) => {
				const variant = action.variant || (index ? "subtle" : "solid");
				return frappe.ui.button({
					...action,
					variant,
					icon_right: variant === "solid" ? "arrow-right" : undefined,
					disabled: locked || action.disabled,
					onclick: () => action.onclick?.(item, this),
				})[0];
			}
		);
		if (item.skippable && !item.done) {
			buttons.push(this.make_button(__("Skip"), () => this.skip(item)));
		}
		return buttons;
	}

	make_button(label, onclick) {
		return frappe.ui.button({ label, variant: "subtle", onclick })[0];
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

	has_body(item) {
		return Boolean(
			item.description ||
				item.actions?.length ||
				(item.skippable && !item.done) ||
				(!this.is_finished(item) && item.locked)
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
