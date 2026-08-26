frappe.provide("frappe.data_import");

/** Static tree preview using the same markup and styles as desk Tree View. */
frappe.data_import.ImportTreePreview = class ImportTreePreview {
	constructor({ wrapper, doctype, preview_data, on_row_click }) {
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.preview_data = preview_data;
		this.on_row_click = on_row_click;
		this.icon_set = {
			open: frappe.utils.icon("folder-open", "md"),
			closed: frappe.utils.icon("folder", "md"),
			leaf: frappe.utils.icon("dot", "xs"),
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
		const { roots, children_by_parent } = this._build_tree(nodes);
		const root_label = __("{0} Tree", [__(this.doctype)]);
		const root_icon = roots.length
			? `<span class="node-parent">${this.icon_set.open}</span>`
			: "";

		this.wrapper.html(`
			<div class="import-tree-preview-panel">
				${this.get_status_banner_html(tree_preview)}
				<div class="import-tree-header">
					<div class="import-tree-title">
						${root_icon}
						<span class="import-tree-doctype-label">${frappe.utils.escape_html(root_label)}</span>
					</div>
					<div class="btn-group">
						<button type="button" class="btn btn-default btn-xs" data-action="expand_all">
							${__("Expand All")}
						</button>
						<button type="button" class="btn btn-default btn-xs" data-action="collapse_all">
							${__("Collapse All")}
						</button>
					</div>
				</div>
				<div class="import-tree-body"></div>
				<div class="text-muted margin-top text-medium">${footer}</div>
			</div>
		`);

		const $tree = $('<div class="tree with-skeleton">').appendTo(
			this.wrapper.find(".import-tree-body")
		);
		const $root_children = $('<ul class="tree-children">').appendTo($tree);
		roots.forEach((node) => this.render_node(node, $root_children, children_by_parent));

		frappe.utils.bind_actions_with_object(this.wrapper, this);
	}

	/** Issue banner only (empty nodes or tree structure warnings). */
	get_status_banner_html(tree_preview) {
		const nodes = tree_preview.nodes || [];
		const warning_count = tree_preview.tree_warnings?.length || 0;

		if (!nodes.length) {
			return this.get_form_message_html(
				__("No valid tree nodes found in the import file."),
				"yellow"
			);
		}

		if (!warning_count) {
			return "";
		}

		const warning_label =
			warning_count === 1
				? __("1 tree structure warning found.")
				: __("{0} tree structure warnings found.", [warning_count]);

		return this.get_form_message_html(
			`${warning_label}<br/>${__(
				"See warning icons on nodes below or check the Warnings section."
			)}`,
			"yellow"
		);
	}

	get_form_message_html(message, color) {
		return `<div class="form-message ${color} import-tree-status-alert"><div>${message}</div></div>`;
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

		if (expandable && children.length) {
			$li.addClass("opened");
		}

		const $link = $('<span class="tree-link">').appendTo($li);
		const icon_html = expandable
			? `<span class="node-parent">${
					children.length ? this.icon_set.open : this.icon_set.closed
			  }</span>`
			: `<span>${this.icon_set.leaf}</span>`;
		$(icon_html).appendTo($link);

		$(`<a class="tree-label" data-name="${frappe.utils.escape_html(node.id)}">`)
			.html(this.get_node_label_html(node))
			.appendTo($link);

		const $children = $('<ul class="tree-children">').appendTo($li);
		children.forEach((child) => this.render_node(child, $children, children_by_parent));

		if (!expandable || !children.length) {
			$children.hide();
		}

		$link.on("click", (e) => {
			e.preventDefault();
			if (expandable && children.length) {
				this.toggle_children($li, $link, $children);
			}
			frappe.dom.activate($link.closest(".tree"), $link, "tree-link");
			this.on_row_click?.(node.row_number);
		});

		$link.hover(
			() => $li.addClass("hover-active"),
			() => $li.removeClass("hover-active")
		);

		if (node.orphan) {
			$li.addClass("import-tree-node-orphan");
		}
	}

	get_node_label_html(node) {
		let label = frappe.utils.escape_html(node.label);
		if (node.warnings?.length) {
			const title = frappe.utils.escape_html(
				node.warnings.map((warning) => strip_html(warning)).join(" ")
			);
			label += ` <span class="text-warning" title="${title}">${frappe.utils.icon(
				"triangle-alert",
				"sm"
			)}</span>`;
		}
		if (node.orphan) {
			label += ` <span class="text-muted">(${__("unlinked")})</span>`;
		}
		label += ` <span class="text-muted import-tree-row-number">#${node.row_number}</span>`;
		return label;
	}

	toggle_children($parent, $link, $children) {
		const is_open = $parent.hasClass("opened");
		$parent.toggleClass("opened", !is_open);
		$children.toggle(!is_open);
		const $icon_parent = $link.find(".node-parent");
		if ($icon_parent.length) {
			$icon_parent.html(!is_open ? this.icon_set.open : this.icon_set.closed);
		}
	}

	expand_all() {
		const $tree = this.wrapper.find(".tree");
		$tree.find(".tree-node, .tree").addClass("opened");
		$tree.find(".tree-children").show();
		$tree.find(".node-parent").html(this.icon_set.open);
		this._set_header_folder_icon(true);
	}

	collapse_all() {
		const $tree = this.wrapper.find(".tree");
		$tree.find(".tree-node").removeClass("opened");
		$tree.find(".tree-children").hide();
		$tree.find(".node-parent").html(this.icon_set.closed);
		$tree.children(".tree-children").show();
		this._set_header_folder_icon(false);
	}

	_set_header_folder_icon(open) {
		const $icon = this.wrapper.find(".import-tree-header .node-parent");
		if ($icon.length) {
			$icon.html(open ? this.icon_set.open : this.icon_set.closed);
		}
	}
};
