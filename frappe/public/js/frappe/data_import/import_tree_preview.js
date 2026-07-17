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
			open: frappe.utils.icon("folder-open", "sm", "", "", "", true),
			closed: frappe.utils.icon("folder", "sm", "", "", "", true),
			leaf: frappe.utils.icon("circle", "xs", "", "", "", true),
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
		const header_folder = frappe.utils.icon("folder", "sm", "", "", "", true);

		this.wrapper.html(`
			<div class="import-tree-preview-panel diw-tree-preview-panel">
				${this.get_status_banner_html(tree_preview)}
				<div class="import-tree-header">
					<div class="import-tree-title">
						<span class="diw-tree-header-icon">${header_folder}</span>
						<span class="import-tree-doctype-label">${frappe.utils.escape_html(root_label)}</span>
					</div>
					<div class="diw-tree-preview-actions">
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
				<div class="diw-tree-filter">
					<label class="diw-tree-filter-input">
						<span class="diw-tree-filter-icon">${this.icon_set.search}</span>
						<input type="search" class="form-control input-sm" placeholder="${__(
							"Filter nodes"
						)}" autocomplete="off" />
					</label>
				</div>
				<div class="import-tree-box">
					<div class="import-tree-body"></div>
					<div class="diw-tree-preview-footer">
						<span class="diw-tree-preview-count">${footer}</span>
						<div class="diw-tree-preview-legend">
							<span class="diw-tree-legend-item">
								<span class="diw-tree-legend-icon">${this.icon_set.closed}</span>
								${__("Group")}
							</span>
							<span class="diw-tree-legend-item">
								<span class="diw-tree-legend-icon diw-tree-legend-icon--leaf">${this.icon_set.leaf}</span>
								${__("Leaf")}
							</span>
						</div>
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
			css_class: "import-tree-status-alert",
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
		const $li = $('<li class="tree-node">').appendTo($parent);
		const is_open = expandable && children.length > 0;

		if (is_open) {
			$li.addClass("opened");
		}

		const $row = $('<div class="diw-tree-row">').appendTo($li);
		const $main = $('<span class="tree-link diw-tree-row-main">').appendTo($row);

		if (expandable) {
			$('<span class="diw-tree-chevron">')
				.html(is_open ? this.icon_set.chevron_open : this.icon_set.chevron_closed)
				.appendTo($main);
			$('<span class="node-parent diw-tree-node-icon">')
				.html(is_open ? this.icon_set.open : this.icon_set.closed)
				.appendTo($main);
		} else {
			$(
				'<span class="diw-tree-chevron diw-tree-chevron--spacer" aria-hidden="true"></span>'
			).appendTo($main);
			$('<span class="diw-tree-node-icon diw-tree-node-icon--leaf">')
				.html(this.icon_set.leaf)
				.appendTo($main);
		}

		$('<a class="tree-label diw-tree-label">')
			.attr("data-name", node.id)
			.html(this.get_node_label_html(node))
			.appendTo($main);

		$('<span class="diw-tree-row-meta">').html(this.get_node_meta_html(node)).appendTo($row);

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
			parts.push(`<span class="text-muted diw-tree-orphan-tag">(${__("unlinked")})</span>`);
		}
		parts.push(`<span class="import-tree-row-number">#${node.row_number}</span>`);
		return parts.join("");
	}

	toggle_children($parent, $link, $children) {
		const is_open = $parent.hasClass("opened");
		const now_open = !is_open;
		$parent.toggleClass("opened", now_open);
		$children.toggle(now_open);
		this._sync_row_icons($link, now_open);
	}

	/** Keep chevron and folder icons in sync after expand/collapse. */
	_sync_row_icons($link, is_open) {
		const $chevron = $link.find(".diw-tree-chevron:not(.diw-tree-chevron--spacer)");
		if ($chevron.length) {
			$chevron.html(is_open ? this.icon_set.chevron_open : this.icon_set.chevron_closed);
		}
		const $folder = $link.find(".diw-tree-node-icon.node-parent");
		if ($folder.length) {
			$folder.html(is_open ? this.icon_set.open : this.icon_set.closed);
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
			$nodes.removeClass("diw-tree-node-hidden");
			return;
		}

		$nodes.addClass("diw-tree-node-hidden");

		$nodes.each((_, el) => {
			const $li = $(el);
			const label = $li.find("> .diw-tree-row .diw-tree-label").first().text().toLowerCase();
			const row_number = $li
				.find("> .diw-tree-row .import-tree-row-number")
				.text()
				.toLowerCase();
			const row_query = query.replace(/^#/, "");
			const matches =
				label.includes(query) ||
				row_number.includes(query) ||
				(row_query && String(row_number).replace("#", "").includes(row_query));

			if (matches) {
				$li.removeClass("diw-tree-node-hidden");
				$li.parents(".tree-node").removeClass("diw-tree-node-hidden");
			}
		});

		// Expand branches that contain visible nodes.
		$tree.find(".tree-node:not(.diw-tree-node-hidden)").each((_, el) => {
			const $li = $(el);
			if ($li.find(".tree-children .tree-node:not(.diw-tree-node-hidden)").length) {
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
