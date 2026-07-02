// "My Workspaces" picker -- lets the user curate which workspaces appear in their workspace
// selector, across apps. Two draggable areas: the left is a preview of the selector (their
// chosen workspaces, reorderable); the right is the full pool of permitted workspaces, browsable
// app-by-app (plus a "Private" group for the user's own workspaces and a "Custom" group for
// public workspaces that belong to no app). All data comes from `frappe.boot`; only the
// selection is saved.

// sentinel app value for the user's private (`for_user`) workspaces in the pool dropdown
const PRIVATE_GROUP = "__private__";
// sentinel app value for public custom workspaces that belong to no app
const CUSTOM_GROUP = "__custom__";

frappe.ui.WorkspacePicker = class WorkspacePicker {
	constructor() {
		this.make();
	}

	make() {
		this.selection = this.initial_selection();

		this.dialog = new frappe.ui.Dialog({
			title: __("Workspaces"),
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "picker" }],
			primary_action_label: __("Save"),
			primary_action: () => this.save(),
		});

		this.$body = $(this.dialog.fields_dict.picker.$wrapper);
		this.render();
		this.dialog.show();
	}

	// Start from the user's saved selection; if they have none, seed it with the current app's
	// workspaces (what the selector shows by default) so they can trim from there.
	initial_selection() {
		let sel = (frappe.boot.user_workspaces || []).slice();
		if (!sel.length) {
			sel = ((frappe.current_app && frappe.current_app.workspaces) || []).slice();
		}
		return sel.filter((name) => this.has_meta(name));
	}

	has_meta(name) {
		return !!frappe.workspaces[frappe.router.slug(name)];
	}

	get_ws(name) {
		return frappe.workspaces[frappe.router.slug(name)] || { name, title: name };
	}

	render() {
		this.$body.html(`
			<div class="workspace-picker">
				<div class="ws-pane ws-pane-selection">
					<div class="ws-pane-head">
						<span>${__("Your workspaces")}</span>
						<button class="ws-clear-all btn btn-ghost">${__("Clear")}</button>
					</div>
											<div class="ws-pane-sub">${__("Workspaces shown in your sidebar switcher. Drag to reorder.")}</div>
					<div class="ws-list ws-selection"></div>
				</div>
				<div class="ws-pane ws-pane-pool">
					<div class="ws-pane-head">${__("All workspaces")}</div>
					<div class="ws-app-picker"></div>
					<div class="ws-list ws-pool"></div>
				</div>
			</div>
		`);

		this.$selection = this.$body.find(".ws-selection");
		this.$pool = this.$body.find(".ws-pool");

		this.$body.find(".ws-clear-all").on("click", () => this.clear_all());

		this.render_app_picker();
		this.render_selection();
		this.render_pool();
		this.setup_selection_sortable();
		this.setup_pool_sortable();
	}

	clear_all() {
		if (!this.selection.length) return;
		this.selection = [];
		this.render_selection();
		this.render_pool();
	}

	render_app_picker() {
		// only apps that expose workspaces are worth listing
		this.apps = (frappe.boot.app_data || []).filter((a) => (a.workspaces || []).length);
		this.current_app_name =
			(frappe.current_app && frappe.current_app.app_name) ||
			(this.apps[0] && this.apps[0].app_name);

		let options = this.apps
			.map(
				(a) =>
					`<option value="${frappe.utils.escape_html(a.app_name)}" ${
						a.app_name === this.current_app_name ? "selected" : ""
					}>${frappe.utils.escape_html(a.app_title)}</option>`
			)
			.join("");

		// offer public app-less custom workspaces as their own group
		if (this.get_custom_workspaces().length) {
			options += `<option value="${CUSTOM_GROUP}" ${
				this.current_app_name === CUSTOM_GROUP ? "selected" : ""
			}>${__("Custom")}</option>`;
		}

		// offer the user's private workspaces as their own group
		if (this.get_private_workspaces().length) {
			options += `<option value="${PRIVATE_GROUP}" ${
				this.current_app_name === PRIVATE_GROUP ? "selected" : ""
			}>${__("Private")}</option>`;
		}

		let $picker = this.$body.find(".ws-app-picker");
		$picker.html(`<select class="form-control">${options}</select>`);
		$picker.find("select").on("change", (e) => {
			this.current_app_name = e.target.value;
			this.render_pool();
			this.setup_pool_sortable();
		});
	}

	// the user's own private (`for_user`) workspaces, by name
	get_private_workspaces() {
		return Object.values(frappe.workspaces || {})
			.filter((ws) => !ws.public && ws.for_user === frappe.session.user)
			.map((ws) => ws.name);
	}

	// public custom (user-created, non-standard) workspaces that belong to no app, by name
	get_custom_workspaces() {
		return Object.values(frappe.workspaces || {})
			.filter((ws) => ws.public && !ws.standard && !ws.app)
			.map((ws) => ws.name);
	}

	render_selection() {
		this.$selection.empty();
		if (!this.selection.length) {
			this.$selection.append(
				`<div class="ws-empty text-muted">${__("Drag workspaces here")}</div>`
			);
			return;
		}
		this.selection.forEach((name) => this.$selection.append(this.selection_item(name)));
	}

	render_pool() {
		let names;
		if (this.current_app_name === PRIVATE_GROUP) {
			names = this.get_private_workspaces();
		} else if (this.current_app_name === CUSTOM_GROUP) {
			names = this.get_custom_workspaces();
		} else {
			let app = this.apps.find((a) => a.app_name === this.current_app_name);
			names = (app && app.workspaces) || [];
		}
		this.$pool.empty();
		names
			.filter((name) => this.has_meta(name))
			.forEach((name) => this.$pool.append(this.pool_item(name)));
	}

	item(name, cls) {
		const ws = this.get_ws(name);
		const icon = ws.icon
			? frappe.utils.icon(ws.icon, "md")
			: frappe.utils.desktop_icon(ws.title || name, "gray", "sm", "Solid");
		return $(`
			<div class="ws-item ${cls || ""}" data-name="${frappe.utils.escape_html(name)}">
				<span class="ws-item-icon">${icon}</span>
				<span class="ws-item-label">${frappe.utils.escape_html(ws.title || name)}</span>
			</div>
		`);
	}

	selection_item(name) {
		let $el = this.item(name, "ws-selection-item");
		$el.prepend(
			`<span class="ws-item-handle">${frappe.utils.icon("grip-vertical", "sm")}</span>`
		);
		let $remove = $(
			`<button class="ws-item-remove" title="${__("Remove")}">${frappe.utils.icon(
				"x",
				"sm"
			)}</button>`
		);
		$remove.on("click", () => this.remove_from_selection(name));
		$el.append($remove);
		return $el;
	}

	pool_item(name) {
		// already-chosen workspaces are shown disabled (can't be added twice)
		let selected = this.selection.includes(name);
		return this.item(name, "ws-pool-item" + (selected ? " is-selected" : ""));
	}

	setup_selection_sortable() {
		this.selection_sortable = new Sortable(this.$selection[0], {
			group: { name: "ws", pull: false, put: true },
			handle: ".ws-item-handle",
			animation: 150,
			ghostClass: "ws-item-ghost",
			// a workspace dragged in from the pool: capture its name, drop the cloned node, and
			// re-render both lists from `this.selection` (our single source of truth)
			onAdd: (evt) => {
				const name = $(evt.item).attr("data-name");
				$(evt.item).remove();
				if (name && !this.selection.includes(name)) this.selection.push(name);
				this.render_selection();
				this.render_pool();
			},
			onUpdate: () => this.sync_order(),
		});
	}

	setup_pool_sortable() {
		if (this.pool_sortable) this.pool_sortable.destroy();
		this.pool_sortable = new Sortable(this.$pool[0], {
			group: { name: "ws", pull: "clone", put: false },
			sort: false,
			animation: 150,
			filter: ".is-selected",
		});
	}

	sync_order() {
		this.selection = $.map(this.$selection.find(".ws-item"), (el) => $(el).attr("data-name"));
	}

	remove_from_selection(name) {
		this.selection = this.selection.filter((n) => n !== name);
		this.render_selection();
		this.render_pool();
	}

	async save() {
		this.sync_order();
		await frappe.xcall("frappe.desk.desktop.save_workspace_preferences", {
			workspaces: JSON.stringify(this.selection),
		});
		this.dialog.hide();
		frappe.show_alert({ message: __("Workspaces updated"), indicator: "green" });
		// reload so the sidebar selector reflects the new preference
		setTimeout(() => location.reload(), 600);
	}
};
