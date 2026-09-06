frappe.provide("frappe.data_import");

/** Static tree preview for the import wizard — desk tree markup with mockup-aligned chrome. */
frappe.data_import.ImportTreePreview = class ImportTreePreview {
	constructor({ wrapper, doctype, preview_data, on_row_click, events, readonly }) {
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.preview_data = preview_data;
		this.on_row_click = on_row_click;
		// events.on_change(overrides_map) — persist the move / group edits to the form.
		this.events = events || {};
		// readonly: true when import is complete — hides edit actions.
		this.readonly = Boolean(readonly);
		this.icon_set = {
			chevron_open: frappe.utils.icon("chevron-down", "xs", "", "", "", true),
			chevron_closed: frappe.utils.icon("chevron-right", "xs", "", "", "", true),
			search: frappe.utils.icon("search", "sm", "", "", "", true),
		};
		this.refresh();
	}

	get_nodes() {
		return this.preview_data?.tree_preview?.nodes || [];
	}

	refresh() {
		const tree_preview = this.preview_data?.tree_preview;
		if (!tree_preview) {
			this._destroy_dropdowns();
			this.wrapper.empty();
			return;
		}

		this.editable = Boolean(tree_preview.editable);
		this.is_group_editable = Boolean(tree_preview.is_group_editable);
		this._destroy_dropdowns();

		const nodes = tree_preview.nodes || [];
		if (!nodes.length) {
			this.wrapper.html(this.get_status_banner_html(tree_preview));
			return;
		}

		const total_nodes = tree_preview.total_nodes ?? nodes.length;
		const footer =
			total_nodes === 1 ? __("1 node") : __("Tree preview of {0} nodes", [total_nodes]);
		const { roots, children_by_parent } = this._build_tree(nodes);

		this.wrapper.html(`
			<div class="import-tree-preview-panel">
				${this.get_status_banner_html(tree_preview)}
				<div class="import-tree-actions flex items-center justify-between gap-2 mb-2">
					<label class="diw-tree-filter-input flex items-center gap-2 flex-1 min-w-0 max-w-lg border rounded px-2 bg-surface-base">
						<span class="diw-tree-filter-icon inline-flex text-muted">${this.icon_set.search}</span>
						<input type="search" class="form-control input-sm" placeholder="${__(
							"Filter nodes"
						)}" autocomplete="off" />
					</label>
					<div class="inline-flex items-center gap-1 shrink-0">
						${
							!this.readonly && this.has_edited_nodes()
								? frappe.ui.button.html({
										label: __("Reset all"),
										variant: "outline",
										theme: "red",
										attrs: { "data-action": "reset_all" },
								  })
								: ""
						}
						${frappe.ui.button.html({
							label: __("Expand all"),
							variant: "outline",
							attrs: { "data-action": "expand_all" },
						})}
						${frappe.ui.button.html({
							label: __("Collapse all"),
							variant: "outline",
							attrs: { "data-action": "collapse_all" },
						})}
					</div>
				</div>
				<div class="import-tree-box flex flex-col border rounded overflow-hidden bg-surface-base">
					<div class="import-tree-body flex-1 overflow-auto border-0 bg-transparent"></div>
					<div class="diw-tree-preview-footer flex items-center shrink-0 border-t text-sm text-muted px-3 py-2 bg-surface-gray-1">
						<span class="whitespace-nowrap">${footer}</span>
					</div>
				</div>
			</div>
		`);

		const $tree = $('<div class="tree with-skeleton">').appendTo(
			this.wrapper.find(".import-tree-body")
		);
		const $root_children = $('<ul class="tree-children">').appendTo($tree);
		roots.forEach((node) => this.render_node(node, $root_children, children_by_parent));
		this._sync_tree_action_button_states();

		this.wrapper.find(".diw-tree-filter-input input").on("input.diw_tree_filter", (e) => {
			this.filter_tree(e.target.value);
		});

		frappe.utils.bind_actions_with_object(this.wrapper, this);
	}

	/** Issue banner only (empty nodes or tree structure warnings). */
	get_status_banner_html(tree_preview) {
		const nodes = tree_preview.nodes || [];
		const warning_count = tree_preview.tree_warnings?.length || 0;

		if (!nodes.length) {
			return this.get_form_message_html({
				title: __("No valid tree nodes found in the import file."),
				theme: "yellow",
			});
		}

		if (!warning_count) {
			return "";
		}

		const warning_label =
			warning_count === 1
				? __("1 warning found.")
				: __("{0} warnings found.", [warning_count]);

		return this.get_form_message_html({
			title: warning_label,
			description: __("See warning icons on nodes below or check the Warnings section."),
			theme: "yellow",
		});
	}

	get_form_message_html({ title, description = "", theme = "yellow" } = {}) {
		return frappe.ui.alert.html({
			title,
			description,
			theme,
			css_class: "import-tree-status-alert mb-2",
		});
	}

	/**
	 * Build parent→children maps for rendering.
	 * Nodes in a parent cycle (common after a partial Reset) are not reachable from
	 * any root — promote them to top-level orphans so they stay visible and editable.
	 */
	_build_tree(nodes) {
		const nodes_by_id = {};
		nodes.forEach((node) => {
			nodes_by_id[node.id] = node;
		});

		const children_by_parent = {};
		const roots = [];

		for (const node of nodes) {
			const parent_id = node.parent;
			if (node.orphan || !parent_id || !nodes_by_id[parent_id]) {
				roots.push(node);
			} else {
				children_by_parent[parent_id] = children_by_parent[parent_id] || [];
				children_by_parent[parent_id].push(node);
			}
		}

		// Walk from current roots. Anything never reached is a cycle fragment.
		const reachable = new Set();
		const stack = roots.map((node) => node.id);
		while (stack.length) {
			const id = stack.pop();
			if (reachable.has(id)) {
				continue;
			}
			reachable.add(id);
			for (const child of children_by_parent[id] || []) {
				stack.push(child.id);
			}
		}

		for (const node of nodes) {
			if (reachable.has(node.id)) {
				continue;
			}
			// Show as a top-level orphan and detach from the cycle so render cannot recurse.
			node.orphan = true;
			roots.push(node);
			const parent_id = node.parent;
			if (parent_id && children_by_parent[parent_id]) {
				children_by_parent[parent_id] = children_by_parent[parent_id].filter(
					(child) => child.id !== node.id
				);
			}
		}

		return { roots, children_by_parent };
	}

	/** Tear down Action dropdowns before wiping the tree DOM. */
	_destroy_dropdowns() {
		for (const dropdown of this._dropdowns || []) {
			dropdown.destroy?.();
		}
		this._dropdowns = [];
	}

	render_node(node, $parent, children_by_parent) {
		const children = children_by_parent[node.id] || [];
		const expandable = cint(node.is_group) || children.length > 0;
		const $li = $('<li class="tree-node block w-full list-none m-0">').appendTo($parent);
		const is_open = expandable && children.length > 0;

		if (is_open) {
			$li.addClass("opened");
		}

		const $row = $(
			'<div class="diw-tree-row relative flex items-center gap-2 w-full cursor-pointer rounded-sm px-2 py-1">'
		)
			.attr("data-row-number", node.row_number)
			.appendTo($li);
		const $main = $(
			'<span class="tree-link diw-tree-row-main flex items-center gap-1 flex-1 min-w-0 text-sm">'
		).appendTo($row);

		// Expandable: chevron only. Leaves: same-width spacer so labels line up with siblings.
		if (expandable) {
			$(
				'<span class="diw-tree-chevron inline-flex size-4 items-center justify-center text-muted">'
			)
				.html(is_open ? this.icon_set.chevron_open : this.icon_set.chevron_closed)
				.appendTo($main);
		} else {
			$(
				'<span class="diw-tree-chevron diw-tree-chevron--spacer invisible pointer-events-none inline-flex size-4" aria-hidden="true">'
			).appendTo($main);
		}

		$('<a class="tree-label diw-tree-label flex-1 min-w-0 truncate">')
			.toggleClass("text-ink-orange-7", Boolean(node.orphan))
			.attr("data-name", node.id)
			.html(this.get_node_label_html(node))
			.appendTo($main);

		const $meta = $(
			'<span class="diw-tree-row-meta inline-flex items-center justify-end gap-1 shrink-0 text-xs ps-2">'
		)
			.html(this.get_node_meta_html(node))
			.appendTo($row);

		// Always show edited state styling, even when readonly
		$li.toggleClass("is-edited", this.is_edited(node));
		// Only show Actions button when editing is allowed (not readonly)
		if (this.can_edit_node()) {
			this.mount_node_actions(node, $meta);
		}

		const $children = $('<ul class="tree-children">').appendTo($li);
		children.forEach((child) => this.render_node(child, $children, children_by_parent));

		if (!expandable || !children.length) {
			$children.hide();
		}

		$row.on("click", (e) => {
			// Clicking the row's Actions button (or anything inside it) must not
			// expand/collapse the branch — only the row body toggles.
			if ($(e.target).closest(".diw-tree-node-actions").length) {
				return;
			}
			e.preventDefault();
			if (expandable && children.length) {
				this.toggle_children($li, $main, $children);
			}
			frappe.dom.activate($row.closest(".tree"), $main, "tree-link");
			this.on_row_click?.(node.row_number);
		});

		$row.hover(
			() => $li.addClass("hover-active"),
			() => $li.removeClass("hover-active")
		);

		if (node.orphan) {
			$li.addClass("import-tree-node-orphan");
		}
	}

	get_node_label_html(node) {
		return frappe.utils.escape_html(node.label);
	}

	get_node_meta_html(node) {
		const parts = [];
		// Always show edited badge if node was modified, even when readonly
		if (this.is_edited(node)) {
			parts.push(
				frappe.ui.badge.html({
					label: __("edited"),
					theme: "blue",
					size: "sm",
					css_class: "diw-tree-edited-badge",
				})
			);
		}
		if (node.warnings?.length) {
			const title = frappe.utils.escape_html(
				node.warnings.map((warning) => strip_html(warning)).join(" ")
			);
			parts.push(
				`<span class="text-warning diw-tree-warning-icon" title="${title}">${frappe.utils.icon(
					"triangle-alert",
					"sm",
					"",
					"",
					"",
					true
				)}</span>`
			);
		}
		if (node.orphan) {
			parts.push(`<span class="text-muted text-xs">(${__("unlinked")})</span>`);
		}
		return parts.join("");
	}

	toggle_children($parent, $link, $children) {
		const is_open = $parent.hasClass("opened");
		const now_open = !is_open;
		$parent.toggleClass("opened", now_open);
		$children.toggle(now_open);
		this._sync_row_icons($link, now_open);
		this._sync_tree_action_button_states();
	}

	/** Update Expand/Collapse action buttons based on current branch state. */
	_sync_tree_action_button_states() {
		const $tree = this.wrapper.find(".tree");
		const $expand_btn = this.wrapper.find('[data-action="expand_all"]');
		const $collapse_btn = this.wrapper.find('[data-action="collapse_all"]');

		if (!$tree.length || (!$expand_btn.length && !$collapse_btn.length)) {
			return;
		}

		const $branches = $tree
			.find(".tree-node")
			.filter((_, el) => $(el).children(".tree-children").children(".tree-node").length > 0);

		const branch_count = $branches.length;
		const open_count = $branches.filter(".opened").length;
		const all_expanded = branch_count > 0 && open_count === branch_count;
		const all_collapsed = branch_count > 0 && open_count === 0;

		$expand_btn.prop("disabled", all_expanded);
		$collapse_btn.prop("disabled", all_collapsed);
	}

	/** Keep expand/collapse chevron in sync after toggle. */
	_sync_row_icons($link, is_open) {
		const $chevron = $link.find(".diw-tree-chevron:not(.diw-tree-chevron--spacer)");
		if ($chevron.length) {
			$chevron.html(is_open ? this.icon_set.chevron_open : this.icon_set.chevron_closed);
		}
	}

	expand_all() {
		const $tree = this.wrapper.find(".tree");
		$tree.find(".tree-node, .tree").addClass("opened");
		$tree.find(".tree-children").show();
		$tree.find(".diw-tree-row-main").each((_, main) => {
			this._sync_row_icons($(main), true);
		});
		this._sync_tree_action_button_states();
	}

	collapse_all() {
		const $tree = this.wrapper.find(".tree");
		$tree.find(".tree-node").removeClass("opened");
		$tree.find(".tree-children").hide();
		$tree.children(".tree-children").show();
		$tree.find(".diw-tree-row-main").each((_, main) => {
			const $main = $(main);
			if ($main.find(".diw-tree-chevron:not(.diw-tree-chevron--spacer)").length) {
				this._sync_row_icons($main, false);
			}
		});
		this._sync_tree_action_button_states();
	}

	/** Filter tree rows by label or sheet row number; keep ancestors of matches visible. */
	filter_tree(query) {
		const $tree = this.wrapper.find(".tree");
		if (!$tree.length) return;

		query = (query || "").trim().toLowerCase();
		const $nodes = $tree.find(".tree-node");

		if (!query) {
			$nodes.removeClass("hidden");
			this._sync_tree_action_button_states();
			return;
		}

		$nodes.addClass("hidden");

		$nodes.each((_, el) => {
			const $li = $(el);
			const $row = $li.find("> .diw-tree-row").first();
			const label = $row.find(".diw-tree-label").first().text().toLowerCase();
			const row_number = String($row.attr("data-row-number") || "");
			const row_query = query.replace(/^#/, "");
			const matches = label.includes(query) || (row_query && row_number.includes(row_query));

			if (matches) {
				$li.removeClass("hidden");
				$li.parents(".tree-node").removeClass("hidden");
			}
		});

		// Expand branches that contain visible nodes.
		$tree.find(".tree-node:not(.hidden)").each((_, el) => {
			const $li = $(el);
			if ($li.find(".tree-children .tree-node:not(.hidden)").length) {
				$li.addClass("opened");
				$li.children(".tree-children").show();
				this._sync_row_icons(
					$li.children(".diw-tree-row").find(".diw-tree-row-main").first(),
					true
				);
			}
		});

		this._sync_tree_action_button_states();
	}

	// ---- tree editing (move / group toggle) --------------------------------

	/** Any editing possible at all — needs the parent and/or is_group column mapped, and not readonly. */
	can_edit_node() {
		if (this.readonly) return false;
		return Boolean(this.editable || this.is_group_editable);
	}

	is_edited(node) {
		return (
			(node.parent || null) !== (node.orig_parent || null) ||
			cint(node.is_group) !== cint(node.orig_is_group)
		);
	}

	has_children(node) {
		return this.get_nodes().some((n) => n.parent === node.id);
	}

	can_make_group(node) {
		return this.is_group_editable && !cint(node.is_group);
	}

	can_make_leaf(node) {
		return this.is_group_editable && cint(node.is_group) && !this.has_children(node);
	}

	/** Node id + every id beneath it — invalid move targets (would make a cycle). */
	get_descendant_ids(node) {
		const ids = new Set([node.id]);
		const nodes = this.get_nodes();
		let frontier = [node.id];
		while (frontier.length) {
			const next = [];
			for (const parent_id of frontier) {
				for (const child of nodes) {
					if (child.parent === parent_id && !ids.has(child.id)) {
						ids.add(child.id);
						next.push(child.id);
					}
				}
			}
			frontier = next;
		}
		return ids;
	}

	/** Actions button + dropdown of actions in the row's meta area. */
	mount_node_actions(node, $meta) {
		const $btn = frappe.ui.button({
			label: __("Actions"),
			icon_right: "chevron-down",
			variant: "outline",
			size: "xs",
			css_class: "diw-tree-node-actions",
		});
		$meta.append($btn);
		this._dropdowns.push(
			new frappe.ui.Dropdown({
				trigger: $btn,
				align: "end",
				options: () => this.get_node_menu_items(node),
			})
		);
	}

	get_node_menu_items(node) {
		const items = [];
		if (this.editable) {
			items.push({
				label: __("Move to…"),
				icon: "corner-up-right",
				submenu: () => this.get_move_targets(node),
			});
		}
		if (this.can_make_group(node)) {
			items.push({
				label: __("Mark as group"),
				icon: "folder",
				onclick: () => this.set_group(node, 1),
			});
		}
		if (this.can_make_leaf(node)) {
			items.push({
				label: __("Mark as leaf"),
				icon: "file",
				onclick: () => this.set_group(node, 0),
			});
		}
		if (this.is_edited(node)) {
			items.push({
				label: __("Reset node"),
				icon: "rotate-ccw",
				theme: "red",
				onclick: () => this.reset_node(node),
			});
		}
		return items.length ? items : [{ label: __("No actions available"), disabled: true }];
	}

	/** Valid parents: group nodes, minus self, its descendants, and its current parent. */
	get_move_targets(node) {
		const descendants = this.get_descendant_ids(node);
		const targets = this.get_nodes()
			.filter(
				(n) =>
					cint(n.is_group) &&
					n.id !== node.id &&
					n.id !== node.parent &&
					!descendants.has(n.id)
			)
			.sort((a, b) => (a.label || "").localeCompare(b.label || ""))
			.map((n) => ({
				label: n.label,
				icon: "folder",
				onclick: () => this.apply_move(node, n.id),
			}));

		const items = [];
		if (node.parent) {
			items.push({
				label: __("Top level"),
				icon: "corner-left-up",
				onclick: () => this.apply_move(node, ""),
			});
		}
		items.push(...targets);
		return items.length ? items : [{ label: __("No available parents"), disabled: true }];
	}

	apply_move(node, new_parent_id) {
		node.parent = new_parent_id || null;
		// The user explicitly reparented it, so it is no longer an unlinked/orphan node.
		node.orphan = false;
		this.persist_and_rerender();
	}

	set_group(node, is_group) {
		node.is_group = cint(is_group);
		this.persist_and_rerender();
	}

	reset_node(node) {
		node.parent = node.orig_parent || null;
		node.is_group = cint(node.orig_is_group);
		// Clear client orphan flag; _build_tree re-marks cycle fragments after re-link.
		node.orphan = false;
		this.persist_and_rerender();
	}

	/** True when any node differs from its file/original parent or is_group. */
	has_edited_nodes() {
		return this.get_nodes().some((node) => this.is_edited(node));
	}

	/** Restore every edited node to its original parent / is_group from the file. */
	reset_all() {
		for (const node of this.get_nodes()) {
			if (!this.is_edited(node)) {
				continue;
			}
			node.parent = node.orig_parent || null;
			node.is_group = cint(node.orig_is_group);
			node.orphan = false;
		}
		this.persist_and_rerender();
	}

	/** Rebuild the delta map from the current node state and hand it to the form. */
	get_overrides_map() {
		const map = {};
		for (const node of this.get_nodes()) {
			const delta = {};
			if ((node.parent || null) !== (node.orig_parent || null)) {
				delta.parent = node.parent || "";
			}
			if (cint(node.is_group) !== cint(node.orig_is_group)) {
				delta.is_group = cint(node.is_group);
			}
			if (Object.keys(delta).length) {
				map[node.row_number] = delta;
			}
		}
		return map;
	}

	persist_and_rerender() {
		this.events.on_change?.(this.get_overrides_map());
		this.refresh();
	}
};
