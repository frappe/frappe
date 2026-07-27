frappe.provide("frappe.data_import");

/** Static tree preview for the import wizard — desk tree markup with mockup-aligned chrome. */
frappe.data_import.ImportTreePreview = class ImportTreePreview {
	constructor({ wrapper, doctype, preview_data, on_row_click }) {
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.preview_data = preview_data;
		this.on_row_click = on_row_click;
		this.icon_set = {
			chevron_open: frappe.utils.icon("chevron-down", "xs", "", "", "", true),
			chevron_closed: frappe.utils.icon("chevron-right", "xs", "", "", "", true),
			search: frappe.utils.icon("search", "sm", "", "", "", true),
		};
		this.refresh();
	}

	refresh() {
		const tree_preview = this.preview_data?.tree_preview;
		if (!tree_preview) {
			this.wrapper.empty();
			return;
		}

		const nodes = tree_preview.nodes || [];
		if (!nodes.length) {
			this.wrapper.html(this.get_status_banner_html(tree_preview));
			return;
		}

		const total_nodes = tree_preview.total_nodes ?? nodes.length;
		const footer =
			total_nodes === 1 ? __("1 node") : __("Tree preview of {0} nodes", [total_nodes]);
		const root_label = `${__(this.doctype)} ${__("tree")}`;
		const { roots, children_by_parent } = this._build_tree(nodes);

		this.wrapper.html(`
			<div class="import-tree-preview-panel">
				${this.get_status_banner_html(tree_preview)}
				<div class="import-tree-header flex items-center justify-between gap-4 mb-2">
					<div class="import-tree-title inline-flex items-center gap-2 min-w-0">
						<span class="import-tree-doctype-label text-base-semibold">${frappe.utils.escape_html(
							root_label
						)}</span>
					</div>
				</div>
				<div class="import-tree-actions flex items-center justify-between gap-2 mb-2">
					<label class="diw-tree-filter-input flex items-center gap-2 flex-1 min-w-0 max-w-lg border rounded px-2 bg-surface-base">
						<span class="diw-tree-filter-icon inline-flex text-muted">${this.icon_set.search}</span>
						<input type="search" class="form-control input-sm" placeholder="${__(
							"Filter nodes"
						)}" autocomplete="off" />
					</label>
					<div class="inline-flex items-center gap-1 shrink-0">
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
				? __("1 tree structure warning found.")
				: __("{0} tree structure warnings found.", [warning_count]);

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

	_build_tree(nodes) {
		const nodes_by_id = {};
		nodes.forEach((node) => {
			nodes_by_id[node.id] = node;
		});

		const children_by_parent = {};
		const roots = [];

		for (const node of nodes) {
			const parent_id = node.parent;
			if (node.orphan || (parent_id && !nodes_by_id[parent_id])) {
				roots.push(node);
			} else if (!parent_id) {
				roots.push(node);
			} else {
				children_by_parent[parent_id] = children_by_parent[parent_id] || [];
				children_by_parent[parent_id].push(node);
			}
		}

		return { roots, children_by_parent };
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

		$(
			'<span class="diw-tree-row-meta inline-flex items-center justify-end gap-1 shrink-0 text-xs ps-2">'
		)
			.html(this.get_node_meta_html(node))
			.appendTo($row);

		const $children = $('<ul class="tree-children">').appendTo($li);
		children.forEach((child) => this.render_node(child, $children, children_by_parent));

		if (!expandable || !children.length) {
			$children.hide();
		}

		$row.on("click", (e) => {
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
	}

	/** Filter tree rows by label or sheet row number; keep ancestors of matches visible. */
	filter_tree(query) {
		const $tree = this.wrapper.find(".tree");
		if (!$tree.length) return;

		query = (query || "").trim().toLowerCase();
		const $nodes = $tree.find(".tree-node");

		if (!query) {
			$nodes.removeClass("hidden");
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
	}
};
