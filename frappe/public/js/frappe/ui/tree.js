// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui");

frappe.ui.Tree = class {
	constructor({
		parent,
		label,
		root_value,
		icon_set,
		toolbar,
		expandable,
		with_skeleton = 1,
		// row mode: full-width rows, toolbar rendered as hover actions +
		// context menu instead of the click-injected button group. Embedded
		// consumers (BOM Configurator, dialogs) keep the legacy behavior.
		use_row_actions = false,

		args,
		method,
		get_label,
		on_render,
		on_click,
		on_node_render,
	}) {
		$.extend(this, arguments[0]);
		if (root_value == null) {
			this.root_value = label;
		}
		this.setup_treenode_class();
		this.nodes = {};
		this.wrapper = $('<div class="tree" role="tree">').appendTo(this.parent);
		if (with_skeleton) this.wrapper.addClass("with-skeleton");
		if (this.use_row_actions) {
			this.wrapper.addClass("tree-rows");
			this.setup_context_menu();
		}

		if (!icon_set) {
			this.icon_set = {
				open: frappe.utils.icon("chevron-down", "sm"),
				closed: frappe.utils.is_rtl()
					? frappe.utils.icon("chevron-left", "sm")
					: frappe.utils.icon("chevron-right", "sm"),
				leaf: frappe.utils.icon("circle-small", "xs"),
			};
		}

		this.setup_root_node();
	}

	get_nodes(value, is_root) {
		var args = Object.assign({}, this.args);
		args.parent = value;
		args.is_root = is_root;

		return new Promise((resolve) => {
			frappe.call({
				method: this.method,
				args: args,
				callback: (r) => {
					this.on_get_node && this.on_get_node(r.message);
					resolve(r.message);
				},
			});
		});
	}

	get_all_nodes(value, is_root, label) {
		var args = Object.assign({}, this.args);
		args.label = label || value;
		args.parent = value;
		args.is_root = is_root;

		args.tree_method = this.method;

		return new Promise((resolve) => {
			frappe.call({
				method: "frappe.desk.treeview.get_all_nodes",
				args: args,
				callback: (r) => {
					this.on_get_node && this.on_get_node(r.message, true);
					resolve(r.message);
				},
			});
		});
	}

	setup_treenode_class() {
		let tree = this;
		this.TreeNode = class {
			constructor({ parent, label, parent_label, expandable, is_root, data }) {
				$.extend(this, arguments[0]);
				this.loaded = 0;
				this.expanded = 0;
				if (this.parent_label) {
					this.parent_node = tree.nodes[this.parent_label];
				}

				tree.nodes[this.label] = this;
				tree.make_node_element(this);
				tree.on_render && tree.on_render(this);
			}
		};
	}

	setup_root_node() {
		this.root_node = new this.TreeNode({
			parent: this.wrapper,
			label: this.label,
			parent_label: null,
			expandable: true,
			is_root: true,
			data: {
				value: this.root_value,
			},
		});
		this.expand_node(this.root_node, false);
	}

	refresh() {
		this.selected_node.parent_node && this.load_children(this.selected_node.parent_node, true);
	}

	make_node_element(node) {
		node.$tree_link = $('<span class="tree-link">')
			.attr("data-label", node.label)
			.attr("role", "treeitem")
			.attr("aria-expanded", node.expandable ? "false" : null)
			.data("node", node)
			.appendTo(node.parent);

		node.$ul = $('<ul class="tree-children" role="group">').hide().appendTo(node.parent);

		this.make_icon_and_label(node);
		if (this.toolbar) {
			if (this.use_row_actions) {
				this.make_row_actions(node);
			} else {
				node.$toolbar = this.get_toolbar(node).insertAfter(node.$tree_link);
			}
		}
		if (this.use_row_actions && !node.is_root) {
			this.setup_node_hover_card(node);
		}
	}

	// ─── row mode: node hover card ─────────────────────────────────────────

	setup_node_hover_card(node) {
		// same gate as the generic link preview this card replaces
		if (!(frappe.boot.link_preview_doctypes || []).includes(this.args.doctype)) return;

		node.hover_card = frappe.ui.hover_card(node.$tree_link.find("a.tree-label"), {
			side: "bottom",
			align: "start",
			css_class: "tree-node-hover-panel",
			content: () => this.build_node_hover_card(node),
		});

		// start the fetch on first hover, before the card's open delay
		// elapses — an empty preview then destroys the card before it ever
		// opens, instead of flashing a skeleton and vanishing
		node.$tree_link.one("mouseenter", () => this.get_node_preview(node));
	}

	build_node_hover_card(node) {
		// a previous fetch found nothing worth showing — stay silent
		if (node.preview_empty) return null;

		const $card = $(`
			<div class="tree-hover-card">
				${frappe.ui.skeleton.html({ width: "60%", height: "14px" })}
				${frappe.ui.skeleton.html({ width: "40%", height: "12px", css_class: "mt-2" })}
			</div>
		`);
		this.get_node_preview(node).then((data) => {
			if (!document.body.contains($card[0])) return;
			if (!data) {
				node.hover_card && node.hover_card.close();
				return;
			}
			$card.empty().append(this.render_node_hover_card(node, data));
		});
		return $card;
	}

	get_node_preview(node) {
		if (!node.preview_promise) {
			node.preview_promise = frappe
				.call({
					method: "frappe.desk.link_preview.get_preview_data",
					args: { doctype: this.args.doctype, docname: node.label },
				})
				.then((r) => {
					const data = r.message;
					const meta = frappe.get_meta(this.args.doctype);
					const extra_fields =
						data &&
						Object.keys(data).filter(
							(key) => !["preview_image", "preview_title", "name"].includes(key)
						);
					const has_value_column =
						node.parent && node.parent.children(".balance-area").length;

					// silence beats an empty box: no avatar, no fields, no
					// value column means no card
					if (
						!data ||
						(!meta?.image_field && !extra_fields.length && !has_value_column)
					) {
						node.preview_empty = true;
						node.hover_card && node.hover_card.destroy();
						return null;
					}
					return data;
				})
				.catch(() => {
					node.preview_empty = true;
					node.hover_card && node.hover_card.destroy();
					return null;
				});
		}
		return node.preview_promise;
	}

	render_node_hover_card(node, data) {
		const doctype = this.args.doctype;
		const meta = frappe.get_meta(doctype);
		const title = data.preview_title || data.name;
		const subtitle =
			data.preview_title && data.preview_title !== data.name
				? `${__(doctype)} · ${data.name}`
				: __(doctype);

		const $content = $("<div></div>");
		const $head = $(
			'<div class="tree-hover-card-head flex items-start gap-2.5"></div>'
		).appendTo($content);

		// avatar only when the doctype defines an image field
		if (meta && meta.image_field) {
			$head.append(
				frappe.ui.avatar.html({
					label: title,
					image: data.preview_image || undefined,
					size: "lg",
				})
			);
		}

		const $titles = $('<div class="flex-1 min-w-0"></div>').appendTo($head);
		$('<div class="text-base-semibold text-ink-gray-8 truncate"></div>')
			.text(title)
			.appendTo($titles);
		$('<div class="text-sm text-ink-gray-6 truncate mt-0.5"></div>')
			.text(subtitle)
			.appendTo($titles);

		$(
			frappe.ui.button({
				icon: "external-link",
				variant: "ghost",
				size: "xs",
				title: __("Open"),
				onclick: () => frappe.set_route("Form", doctype, data.name),
			})
		).appendTo($head);

		if (node.expandable) {
			$('<div class="flex gap-1.5 mt-2"></div>')
				.append(frappe.ui.badge({ label: __("Group"), size: "sm" }))
				.appendTo($content);
		}

		const rows = Object.entries(data).filter(
			([key, value]) =>
				!["preview_image", "preview_title", "name"].includes(key) && value != null
		);
		const $balance = node.parent && node.parent.children(".balance-area").first();
		if (rows.length || ($balance && $balance.length)) {
			$('<div class="border-t my-2.5"></div>').appendTo($content);
			const add_row = (label, $value) => {
				const $row = $(
					'<div class="tree-hover-card-row flex items-center justify-between gap-3"></div>'
				).appendTo($content);
				$('<div class="text-sm text-ink-gray-6 shrink-0"></div>')
					.text(label)
					.appendTo($row);
				$value.addClass("value text-sm text-ink-gray-7 truncate").appendTo($row);
			};
			rows.forEach(([label, value]) => {
				// server-side frappe.format output (escaped/translated there)
				add_row(__(label), $("<div></div>").html(value));
			});
			if ($balance && $balance.length) {
				add_row(__("Balance"), $("<div></div>").text($balance.text().trim()));
			}
		}

		return $content;
	}

	// ─── row mode: hover actions + context menu ────────────────────────────

	setup_context_menu() {
		this.context_node = null;
		this.context_menu = new frappe.ui.ContextMenu({
			target: this.wrapper,
			options: () => this.get_node_menu_options(this.context_node),
			on_open: (e) => {
				const $link = $(e.target).closest(".tree-link");
				this.context_node = $link.length ? $link.data("node") : null;
			},
		});
	}

	get_toolbar_items(node) {
		// entries whose condition holds for this node, in declared order
		return Object.values(this.toolbar || {}).filter(
			(obj) => obj.label && (!obj.condition || obj.condition(node))
		);
	}

	get_node_menu_options(node) {
		if (!node) return [];
		// inline entries (e.g. Edit) already have their own button beside the
		// label — repeating them in the menu would be noise. Destructive
		// entries (danger) sink to the end of the menu.
		const items = this.get_toolbar_items(node).filter((obj) => !obj.inline);
		items.sort((a, b) => (a.danger ? 1 : 0) - (b.danger ? 1 : 0));
		return items.map((obj) => {
			// an entry can explain why it's unavailable instead of hiding:
			// get_disabled_reason(node) returning a string renders the row
			// disabled with the reason as its description
			const reason = obj.get_disabled_reason && obj.get_disabled_reason(node);
			return {
				label: obj.get_label ? obj.get_label() : obj.label,
				icon: obj.icon,
				theme: obj.danger ? "red" : undefined,
				disabled: !!reason,
				description: reason || undefined,
				onclick: () => obj.click(node),
			};
		});
	}

	make_row_actions(node) {
		const items = this.get_toolbar_items(node);
		if (!items.length) return;

		const $actions = $('<span class="tree-actions">').appendTo(node.$tree_link);

		// entries flagged `inline` (with an icon) become hover icon-buttons
		// beside the label; everything else collects under the ellipsis,
		// which opens the same menu as right-click
		const inline = items.filter((obj) => obj.inline && obj.icon);
		const overflow = items.filter((obj) => !obj.inline);

		inline.forEach((obj) => {
			const label = obj.get_label ? obj.get_label() : obj.label;
			$(
				frappe.ui.button({
					icon: obj.icon,
					variant: "ghost",
					size: "xs",
					title: label,
					onclick: (e) => {
						e.stopPropagation();
						obj.click(node);
					},
				})
			).appendTo($actions);
		});

		if (overflow.length) {
			const $more = $(
				frappe.ui.button({
					icon: "ellipsis",
					variant: "ghost",
					size: "xs",
					title: __("More actions"),
					onclick: (e) => {
						e.stopPropagation();
						this.context_node = node;
						const rect = e.currentTarget.getBoundingClientRect();
						this.context_menu.open_at(rect.left, rect.bottom + 2);
					},
				})
			).appendTo($actions);
			$more.addClass("tree-more-btn");
		}

		// keep clicks on the action strip from toggling the node
		$actions.on("click", (e) => e.stopPropagation());
	}

	add_node(node, data) {
		var $li = $('<li class="tree-node">');

		return new this.TreeNode({
			parent: $li.appendTo(node.$ul),
			parent_label: node.label,
			label: data.value,
			title: data.title,
			expandable: data.expandable,
			data: data,
		});
	}

	reload_node(node) {
		return this.load_children(node);
	}

	toggle() {
		this.get_selected_node().toggle();
	}

	get_selected_node() {
		return this.selected_node;
	}

	set_selected_node(node) {
		this.selected_node = node;
	}

	load_children(node, deep = false) {
		const value = node.data.value,
			is_root = node.is_root;

		return deep
			? frappe.run_serially([
					() => this.get_all_nodes(value, is_root, node.label),
					(data_list) => this.render_children_of_all_nodes(data_list),
					() => this.set_selected_node(node),
					() => this.on_node_render && this.on_node_render(node, deep),
			  ])
			: frappe.run_serially([
					() => this.get_nodes(value, is_root),
					(data_set) => this.render_node_children(node, data_set),
					() => this.set_selected_node(node),
					() => this.on_node_render && this.on_node_render(node, deep),
			  ]);
	}

	render_children_of_all_nodes(data_list) {
		data_list.map((d) => this.render_node_children(this.nodes[d.parent], d.data));
	}

	render_node_children(node, data_set) {
		node.$ul.empty();
		if (data_set) {
			$.each(data_set, (i, data) => {
				var child_node = this.add_node(node, data);
				child_node.$tree_link.data("node-data", data).data("node", child_node);
			});
		}

		node.expanded = false;

		// As children loaded
		node.loaded = true;
		this.expand_node(node);
	}

	on_node_click(node) {
		this.expand_node(node);
		frappe.dom.activate(this.wrapper, node.$tree_link, "tree-link");
		if (node.$toolbar) this.show_toolbar(node);
	}

	expand_node(node, click = true) {
		this.set_selected_node(node);

		if (click) {
			this.on_click && this.on_click(node);
		}

		if (node.expandable) {
			this.toggle_node(node);
		}
		this.select_link(node);

		node.expanded = !node.expanded;
		node.parent.toggleClass("opened", node.expanded);
		if (node.expandable) {
			node.$tree_link.attr("aria-expanded", String(!!node.expanded));
		}
	}

	toggle_node(node) {
		if (node.expandable && this.get_nodes && !node.loaded) {
			return this.load_children(node);
		}

		// expand children
		if (node.$ul) {
			if (node.$ul.children().length) {
				node.$ul.toggle(!node.expanded);
			}

			// open close icon — scoped to the toggle span (the row's first
			// child); a bare .find(".icon") would also catch the icons inside
			// the row's action buttons
			if (this.icon_set) {
				let $toggle = node.$tree_link.children().first();
				if (!node.expanded) {
					$toggle.html(this.icon_set.open);
				} else {
					$toggle.addClass("node-parent").html(this.icon_set.closed);
				}
			}
		}
	}

	select_link(node) {
		this.wrapper.find(".selected").removeClass("selected");
		node.$tree_link.toggleClass("selected");
	}

	show_toolbar(node) {
		if (this.cur_toolbar) $(this.cur_toolbar).hide();
		this.cur_toolbar = node.$toolbar;
		node.$toolbar.show();
	}

	get_node_label(node) {
		if (this.get_label) {
			return this.get_label(node);
		}
		if (node.title && node.title != node.label) {
			return (
				frappe.utils.escape_html(__(node.title)) +
				` <span class='text-muted'>(${frappe.utils.escape_html(node.label)})</span>`
			);
		} else {
			return frappe.utils.escape_html(__(node.title || node.label));
		}
	}

	make_icon_and_label(node) {
		let icon_html = "";
		if (this.icon_set) {
			if (node.expandable) {
				icon_html = `<span class="node-parent">${this.icon_set.closed}</span>`;
			} else {
				icon_html = `<span>${this.icon_set.leaf}</span>`;
			}
		}

		$(icon_html).appendTo(node.$tree_link);
		$(
			`<a class="tree-label" data-doctype="${frappe.utils.escape_html(
				this.args.doctype
			)}" data-name="${frappe.utils.escape_html(node.label)}"> ${this.get_node_label(
				node
			)}</a>`
		).appendTo(node.$tree_link);

		node.$tree_link.on("click", () => {
			setTimeout(() => {
				this.on_node_click(node);
			}, 100);
		});

		// row mode highlights via CSS :hover; the class is only for the
		// legacy embedded layout (and import_tree_preview's copy of it)
		if (!this.use_row_actions) {
			node.$tree_link.hover(
				function () {
					$(this).parent().addClass("hover-active");
				},
				function () {
					$(this).parent().removeClass("hover-active");
				}
			);
		}
	}

	get_toolbar(node) {
		let $toolbar = $('<span class="tree-node-toolbar btn-group"></span>').hide();

		Object.keys(this.toolbar).map((key) => {
			let obj = this.toolbar[key];
			if (!obj.label) return;
			if (obj.condition && !obj.condition(node)) return;

			var label = obj.get_label ? obj.get_label() : obj.label;
			var $link = $("<button class='btn btn-default btn-xs'></button>")
				.html(label)
				.addClass("tree-toolbar-button " + (obj.btnClass || ""))
				.appendTo($toolbar);
			$link.on("click", () => {
				obj.click(node);
			});
		});

		return $toolbar;
	}
};
