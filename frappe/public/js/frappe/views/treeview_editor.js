// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// Rearranging a hierarchy otherwise means opening each record and editing its
// parent field. This lets a tree view be rearranged in place instead.
//
// Editing works as a session: Edit Tree opens it, drops are recorded rather
// than saved, and Save sends the whole set in one call that either lands
// completely or not at all. A drop writes to the database only when the user
// asks for it, so a stray drag over something like the Chart of Accounts
// cannot quietly re-parent a record.
//
// The tree renders as nested lists:
//
//   div.tree
//     span.tree-link            <- the root node
//     ul.tree-children          <- the root's children
//       li.tree-node
//         span.tree-link
//         ul.tree-children      <- this node's children
//
// so making every children list a sortable in one shared group turns
// "drop a row into a different list" into "give this record a new parent".

frappe.provide("frappe.views");

const SORTABLE_GROUP = "tree-view-editor";
// how long a click is ignored after a drag ends
const CLICK_GUARD_MS = 400;
// hovering a closed group for this long opens it, so you can drop inside
const HOVER_EXPAND_MS = 600;

// fieldtypes a quick edit dialog cannot usefully show
const SKIP_FIELDTYPES = new Set([
	"Table",
	"Table MultiSelect",
	"Button",
	"HTML",
	"Image",
	"Fold",
	"Barcode",
	"Geolocation",
	"Signature",
]);

const LAYOUT_FIELDTYPES = new Set(["Section Break", "Column Break"]);

frappe.views.TreeEditor = class TreeEditor {
	constructor(treeview) {
		this.treeview = treeview;
		this.doctype = treeview.doctype;
		this.active = false;
		// name -> the parent it should end up under
		this.moves = new Map();
		// name -> the parent it had when the session started
		this.origins = new Map();
	}

	get tree() {
		return this.treeview.tree;
	}

	get page() {
		return this.treeview.page;
	}

	get count() {
		return this.moves.size;
	}

	/** Whether this tree can be rearranged at all. */
	get can_edit() {
		return Boolean(
			this.parent_field && this.treeview.can_write && !this.treeview.opts.disable_drag_drop
		);
	}

	get parent_field() {
		const meta = frappe.get_meta(this.doctype);
		if (!meta) return null;

		const parent_field = meta.nsm_parent_field || `parent_${frappe.scrub(this.doctype)}`;
		return frappe.meta.has_field(this.doctype, parent_field) ? parent_field : null;
	}

	// --- wiring ------------------------------------------------------------

	/** Called each time the tree view (re)builds its tree. */
	attach() {
		if (!this.tree || !this.can_edit) return;

		// Some trees hang their nodes under a synthetic root, such as the
		// Company in the Chart of Accounts, which is not a record of this
		// DocType. Dropping there would mean becoming a second root, which
		// nested sets reject, so those roots do not accept drops.
		this.root_is_doc =
			this.treeview.opts.get_tree_root !== false &&
			Boolean(this.tree.root_node?.data?.value);

		this.tree.on_children_render = (node) => this.make_sortable(node);
		this.suppress_link_preview();
		this.make_sortable(this.tree.root_node);

		// a rebuilt tree inside an open session starts draggable again
		if (this.active) this.refresh();
	}

	/**
	 * Frappe pops a link preview over a row once the pointer rests on it.
	 * That card sits on top of the row and swallows the mousedown that would
	 * start a drag, so while editing, keep it from opening.
	 *
	 * The preview is delegated from document.body, so stopping the event on
	 * the way down is enough; rows behave normally again after the session.
	 */
	suppress_link_preview() {
		const wrapper = this.tree.wrapper.get(0);
		if (!wrapper || wrapper.tree_preview_guard) return;
		wrapper.tree_preview_guard = true;

		wrapper.addEventListener(
			"mouseover",
			(event) => {
				if (this.active && event.target.closest(".tree-link")) event.stopPropagation();
			},
			true
		);
	}

	/** Close any preview already on screen when a session opens. */
	close_link_previews() {
		const preview = frappe.app && frappe.app.link_preview;
		preview && preview.clear_all_popovers && preview.clear_all_popovers();
	}

	make_sortable(node) {
		if (!node || !node.$ul || !this.can_edit) return;

		const list = node.$ul.get(0);
		if (!list) return;

		if (list.tree_sortable) list.tree_sortable.destroy();
		node.$ul.addClass("tree-sortable");

		list.tree_sortable = new Sortable(list, {
			disabled: !this.active,
			group: {
				name: SORTABLE_GROUP,
				pull: true,
				put: !node.is_root || this.root_is_doc,
			},
			draggable: "li.tree-node",
			handle: ".tree-link",
			animation: 150,
			fallbackOnBody: true,
			// the outer 40% of a row is the swap zone, which leaves room to
			// aim at a nested list without the list above stealing the drop
			swapThreshold: 0.6,
			ghostClass: "tree-drag-ghost",
			chosenClass: "tree-drag-chosen",
			dragClass: "tree-drag-image",
			onStart: () => this.on_drag_start(),
			onMove: (evt) => this.on_drag_move(evt),
			onEnd: (evt) => this.on_drag_end(evt),
		});
	}

	// --- the session -------------------------------------------------------

	toggle() {
		this.active ? this.discard() : this.start();
	}

	start() {
		if (this.active || !this.can_edit) return;

		this.active = true;
		this.moves.clear();
		this.origins.clear();

		this.close_link_previews();
		this.page.clear_primary_action();
		this.page.set_primary_action(__("Save"), () => this.save(), null, __("Saving"));
		this.page.set_secondary_action(__("Discard"), () => this.discard());
		this.guard_unload();
		this.refresh();

		frappe.show_alert({
			message: __(
				"Drag a row onto a group to move it. Nothing is saved until you press Save."
			),
			indicator: "blue",
		});
	}

	stop() {
		if (!this.active) return;

		this.active = false;
		this.moves.clear();
		this.origins.clear();

		this.release_unload_guard();
		this.page.clear_primary_action();
		this.page.clear_secondary_action();
		this.page.clear_indicator();
		// puts the tree's own "New" button back
		this.treeview.set_primary_action();
		this.refresh();
	}

	save() {
		if (!this.count) return this.stop();

		const moves = Array.from(this.moves, ([name, parent]) => ({ name, parent }));
		frappe.dom.freeze(__("Saving {0} move(s)...", [moves.length]));

		return frappe
			.xcall("frappe.desk.treeview.move_nodes", { doctype: this.doctype, moves })
			.then((result) => {
				frappe.show_alert({
					message: __("Saved {0} move(s)", [result.moved]),
					indicator: "green",
				});
				this.stop();
				this.treeview.make_tree();
			})
			.catch(() => {
				// the server refused one of them and saved none, so stay in the
				// session with everything still on screen
			})
			.finally(() => frappe.dom.unfreeze());
	}

	discard() {
		if (!this.count) return this.stop();

		frappe.confirm(__("Discard {0} unsaved move(s)?", [this.count]), () => {
			this.stop();
			this.treeview.make_tree();
			frappe.show_alert({ message: __("Changes discarded"), indicator: "info" });
		});
	}

	/** Remember where a dropped record should end up. */
	record(name, new_parent, previous_parent) {
		if (!this.active || !name) return;

		if (!this.origins.has(name)) this.origins.set(name, previous_parent || "");

		if (this.origins.get(name) === new_parent) {
			// dragged back where it came from, so there is nothing to save
			this.moves.delete(name);
		} else {
			this.moves.set(name, new_parent);
		}

		this.refresh();
	}

	/**
	 * Re-reading a branch already on screen would replace rows the user has
	 * moved but not yet saved. Opening a branch for the first time is fine,
	 * and is how a closed group is reached mid-drag.
	 */
	blocks_reload(node, deep) {
		if (!this.active || !this.count) return false;
		if (!deep && !(node && node.loaded)) return false;

		frappe.show_alert({
			message: __("Save or discard your moves before reloading the tree."),
			indicator: "orange",
		});
		return true;
	}

	/** A reload or a closed tab would take the unsaved moves with it. */
	guard_unload() {
		if (this.unload_guard) return;

		this.unload_guard = (event) => {
			if (!this.count) return;
			event.preventDefault();
			event.returnValue = "";
			return "";
		};

		window.addEventListener("beforeunload", this.unload_guard);
	}

	release_unload_guard() {
		if (!this.unload_guard) return;
		window.removeEventListener("beforeunload", this.unload_guard);
		this.unload_guard = null;
	}

	// --- what the user sees -------------------------------------------------

	refresh() {
		this.page.wrapper && this.page.wrapper.toggleClass("tree-editing", this.active);
		this.set_dragging(this.active);
		this.refresh_indicator();
		this.refresh_banner();
		this.refresh_moved_rows();

		if (this.$menu_item) {
			// the menu item wraps its text in .menu-item-label
			const $label = this.$menu_item.find(".menu-item-label");
			($label.length ? $label : this.$menu_item).text(
				this.active ? __("Stop Editing") : __("Edit Tree")
			);
		}
	}

	set_dragging(on) {
		if (!this.tree || !this.tree.wrapper) return;

		this.tree.wrapper.toggleClass("tree-draggable", Boolean(on));
		this.tree.wrapper.find("ul.tree-children.tree-sortable").each((i, list) => {
			if (list.tree_sortable) list.tree_sortable.option("disabled", !on);
		});
	}

	refresh_indicator() {
		if (!this.active) return this.page.clear_indicator();

		this.count
			? this.page.set_indicator(__("{0} unsaved", [this.count]), "orange")
			: this.page.set_indicator(__("Editing"), "blue");
	}

	refresh_banner() {
		if (!this.active) {
			this.$banner && this.$banner.remove();
			this.$banner = null;
			return;
		}

		if (!this.$banner) {
			this.$banner = $('<div class="tree-edit-banner"></div>').prependTo(this.page.main);
		}

		this.$banner.text(
			this.count
				? __("Editing — {0} move(s) not saved yet. Press Save to apply them.", [
						this.count,
				  ])
				: __("Editing — drag a row onto a group to give it a new parent.")
		);
	}

	/** Mark the rows sitting somewhere new that is not saved yet. */
	refresh_moved_rows() {
		const wrapper = this.tree && this.tree.wrapper;
		if (!wrapper) return;

		wrapper.find(".tree-link.tree-link-moved").removeClass("tree-link-moved");
		if (!this.active) return;

		this.moves.forEach((parent, name) => {
			wrapper
				.find(`.tree-link[data-label="${CSS.escape(name)}"]`)
				.addClass("tree-link-moved");
		});
	}

	// --- dragging -----------------------------------------------------------

	on_drag_start() {
		this.dragging = true;
		$("body").addClass("tree-dragging");
	}

	on_drag_move(evt) {
		// a branch cannot be dropped inside itself
		if (evt.dragged && evt.to && evt.dragged.contains(evt.to)) return false;

		this.tree.wrapper.find(".tree-drop-target").removeClass("tree-drop-target");
		$(evt.to).addClass("tree-drop-target");

		this.queue_hover_expand(evt.related);
		return true;
	}

	on_drag_end(evt) {
		this.dragging = false;
		this.tree.suppress_click_until = Date.now() + CLICK_GUARD_MS;
		$("body").removeClass("tree-dragging");
		this.tree.wrapper.find(".tree-drop-target").removeClass("tree-drop-target");
		this.cancel_hover_expand();

		if (!this.active) return this.undo_drop(evt);

		const node = this.node_for_item(evt.item);
		const from_node = this.node_for_list(evt.from);
		const to_node = this.node_for_list(evt.to);
		if (!node || !from_node || !to_node) return;

		if (evt.from === evt.to) {
			// Children are listed by name, so a drop that only changes the
			// position among siblings has nothing to save. Put the row back
			// rather than leave an order that will not survive a reload.
			if (evt.oldIndex !== evt.newIndex) {
				frappe.show_alert({
					message: __(
						"Records are listed by name, so the order of siblings cannot be changed."
					),
					indicator: "orange",
				});
				this.undo_drop(evt);
			}
			return;
		}

		this.record(this.doc_name(node), this.parent_value(to_node), this.parent_value(from_node));
	}

	undo_drop(evt) {
		const sibling = evt.from.children[evt.oldIndex];
		sibling ? evt.from.insertBefore(evt.item, sibling) : evt.from.appendChild(evt.item);
	}

	queue_hover_expand(related) {
		const item = $(related).closest("li.tree-node").get(0);
		if (item === this.hover_item) return;

		this.cancel_hover_expand();
		this.hover_item = item;
		if (!item) return;

		const node = this.node_for_item(item);
		if (!node || !node.expandable || node.expanded) return;

		this.hover_timer = setTimeout(() => {
			if (this.dragging) this.tree.expand_node(node, false);
		}, HOVER_EXPAND_MS);
	}

	cancel_hover_expand() {
		clearTimeout(this.hover_timer);
		this.hover_timer = null;
		this.hover_item = null;
	}

	// --- reading the rendered tree ------------------------------------------

	doc_name(node) {
		return node && (node.data?.value || node.label);
	}

	/** What to store in the parent field for a node's children. */
	parent_value(node) {
		return node.is_root && !this.root_is_doc ? "" : this.doc_name(node);
	}

	/** The node whose children live in the given <ul>, or the root node. */
	node_for_list(list) {
		const $li = $(list).closest("li.tree-node");
		return $li.length ? this.node_for_item($li.get(0)) : this.tree.root_node;
	}

	node_for_item(item) {
		return $(item).children(".tree-link").data("node");
	}

	// --- editing one record in place ----------------------------------------

	quick_edit(node) {
		const name = this.doc_name(node);
		if (!name) return;

		frappe.model.with_doctype(this.doctype, () => {
			frappe.db.get_doc(this.doctype, name).then((doc) => this.show_edit_dialog(node, doc));
		});
	}

	show_edit_dialog(node, doc) {
		const editable = frappe.model.can_write(this.doctype);
		const fields = this.get_dialog_fields(editable);

		// nothing this dialog can usefully show, so fall back to the form
		if (!fields.some((df) => !LAYOUT_FIELDTYPES.has(df.fieldtype))) {
			frappe.set_route("Form", this.doctype, doc.name);
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: editable ? __("Edit {0}", [doc.name]) : doc.name,
			size: "large",
			fields,
		});

		this.bind_doc(dialog, doc);
		dialog.set_values(this.values_for(doc, fields));

		if (editable) {
			dialog.set_primary_action(__("Save"), () => this.save_from_dialog(node, doc, dialog));
		}

		dialog.set_secondary_action_label(__("Open Full Form"));
		dialog.set_secondary_action(() => {
			dialog.hide();
			frappe.set_route("Form", this.doctype, doc.name);
		});

		dialog.show();
	}

	/**
	 * depends_on and friends are evaluated against `dialog.doc`. Left alone
	 * that is only the fields the dialog renders, so a rule reading a field
	 * left out of it would silently evaluate false. Expose the stored
	 * document merged with whatever the controls currently hold.
	 */
	bind_doc(dialog, doc) {
		let stored = Object.assign({}, doc);

		Object.defineProperty(dialog, "doc", {
			configurable: true,
			get: () => Object.assign({}, stored, this.control_values(dialog)),
			set: (value) => {
				stored = Object.assign({}, value);
			},
		});
	}

	control_values(dialog) {
		const values = {};

		for (const key in dialog.fields_dict) {
			const field = dialog.fields_dict[key];
			if (field?.df && field.get_value) values[field.df.fieldname] = field.get_value();
		}

		return values;
	}

	get_dialog_fields(editable) {
		const meta = frappe.get_meta(this.doctype);
		if (!meta) return [];

		const fields = [];

		for (const df of meta.fields || []) {
			// a dialog reads better as one scrolling column than as tabs
			if (df.fieldtype === "Tab Break") {
				fields.push({
					fieldtype: "Section Break",
					fieldname: `tree_tab_${df.fieldname}`,
					label: df.label,
				});
				continue;
			}

			if (LAYOUT_FIELDTYPES.has(df.fieldtype)) {
				fields.push(Object.assign({}, df));
				continue;
			}

			if (SKIP_FIELDTYPES.has(df.fieldtype)) continue;
			if (df.hidden || df.read_only || df.is_virtual) continue;
			if (df.permlevel && !frappe.perm.has_perm(this.doctype, df.permlevel, "write"))
				continue;

			const copy = Object.assign({}, df);

			// set_only_once fields can no longer be changed on a saved record
			copy.read_only = editable && !df.set_only_once ? 0 : 1;

			// A fetch_from field makes the link it reads from build a fetch map,
			// and that path calls layout.set_value unbound and then reaches for
			// a frm a dialog does not have. The stored value still shows, and
			// the server applies its own fetch on save.
			delete copy.fetch_from;
			delete copy.fetch_if_empty;

			fields.push(copy);
		}

		return this.prune_layout(fields);
	}

	/**
	 * Leaving out read-only and table fields strands section and column
	 * breaks with nothing under them, which render as empty gaps. Keep only
	 * the breaks that still have a field to introduce.
	 */
	prune_layout(fields) {
		const pruned = [];
		let pending = [];

		for (const df of fields) {
			if (LAYOUT_FIELDTYPES.has(df.fieldtype)) {
				pending.push(df);
				continue;
			}

			pruned.push(...this.collapse_breaks(pending, pruned.length === 0));
			pending = [];
			pruned.push(df);
		}

		return pruned;
	}

	collapse_breaks(pending, at_start) {
		if (!pending.length) return [];

		const sections = pending.filter((df) => df.fieldtype === "Section Break");
		if (sections.length) {
			const labelled = sections.filter((df) => df.label);
			const keep = labelled.length ? labelled : sections;
			return [keep[keep.length - 1]];
		}

		// only column breaks; one is enough, and one before the first field
		// would leave the first column empty
		return at_start ? [] : [pending[pending.length - 1]];
	}

	values_for(doc, fields) {
		const values = {};

		for (const df of fields) {
			if (LAYOUT_FIELDTYPES.has(df.fieldtype)) continue;
			if (df.fieldname in doc) values[df.fieldname] = doc[df.fieldname];
		}

		return values;
	}

	save_from_dialog(node, doc, dialog) {
		// runs the dialog's own mandatory field checks
		if (!dialog.get_values()) return;

		const changed = this.changed_values(dialog, doc);
		if (!Object.keys(changed).length) {
			dialog.hide();
			frappe.show_alert({ message: __("No changes to save"), indicator: "blue" });
			return;
		}

		dialog.disable_primary_action();

		return frappe
			.xcall("frappe.client.set_value", {
				doctype: this.doctype,
				name: doc.name,
				fieldname: changed,
			})
			.then((saved) => {
				dialog.hide();
				frappe.show_alert({ message: __("Saved"), indicator: "green" });
				this.refresh_after_edit(node, saved);
			})
			.finally(() => dialog.enable_primary_action());
	}

	changed_values(dialog, doc) {
		const changed = {};

		for (const key in dialog.fields_dict) {
			const field = dialog.fields_dict[key];
			if (!field?.df || !field.get_value || field.df.read_only) continue;

			const fieldname = field.df.fieldname;
			// skips the synthetic section breaks standing in for tabs
			if (!(fieldname in doc)) continue;

			const value = field.get_value();
			if (!this.same_value(value, doc[fieldname], field.df.fieldtype)) {
				changed[fieldname] = value;
			}
		}

		return changed;
	}

	same_value(a, b, fieldtype) {
		if (["Check", "Int"].includes(fieldtype)) return cint(a) === cint(b);
		if (["Float", "Currency", "Percent"].includes(fieldtype)) return flt(a) === flt(b);
		return cstr(a) === cstr(b);
	}

	/**
	 * Re-read the branch the edited node sits in. If the edit moved it to a
	 * different parent, re-read that branch too so it turns up in its new home.
	 */
	refresh_after_edit(node, saved) {
		if (!this.tree) return;

		// re-reading now would wipe out rows dragged but not yet saved
		if (this.active && this.count) {
			frappe.show_alert({
				message: __("Saved. The tree will catch up when you save your moves."),
				indicator: "blue",
			});
			return;
		}

		if (node.is_root || !node.parent_node) return this.treeview.make_tree();

		const labels = [node.parent_node.label];
		const new_parent = this.parent_field && saved ? saved[this.parent_field] : null;

		if (new_parent && new_parent !== node.parent_node.label && this.tree.nodes[new_parent]) {
			labels.push(new_parent);
		}

		this.reload_branches(labels);
	}

	/**
	 * Re-read the given branches in order. Nodes are looked up by label on
	 * each step rather than held onto, because reloading one branch replaces
	 * the node objects of anything rendered underneath it.
	 */
	reload_branches(labels) {
		const pending = [...new Set(labels.filter(Boolean))];

		return frappe.run_serially(
			pending.map((label) => () => {
				const node = this.tree.nodes && this.tree.nodes[label];
				if (!node || !node.$ul || !document.body.contains(node.$ul.get(0))) return null;
				return this.tree.load_children(node);
			})
		);
	}
};
