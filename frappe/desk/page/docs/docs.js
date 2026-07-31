frappe.provide("frappe.ui");

frappe.pages["docs"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Documentation"),
		single_column: false,
	});

	frappe.docs_browser = new frappe.ui.DocsBrowser({ page, wrapper });
};

frappe.pages["docs"].on_page_show = function () {
	frappe.docs_browser?.show();
};

frappe.ui.DocsBrowser = class DocsBrowser {
	constructor({ page, wrapper }) {
		this.page = page;
		this.wrapper = wrapper;
		this.tree_data = [];
		this.page_paths = new Set();
		this.current_path = null;
		this.setup_layout();
	}

	setup_layout() {
		this.$sidebar = $('<div class="docs-sidebar"></div>').appendTo(this.page.sidebar);
		this.$tree = $('<div class="docs-tree"></div>').appendTo(this.$sidebar);
		this.$content = $(frappe.render_template("docs")).appendTo(this.page.main);
		this.$reading = this.$content.find(".docs-reading-pane");
		this.$state = this.$content.find(".docs-state");
		this.$state_message = this.$content.find(".docs-state-content");

		this.$tree.on("click", ".docs-tree-node", (event) => {
			event.preventDefault();
			const path = $(event.currentTarget).data("path");
			if (path === undefined) {
				return;
			}
			this.navigate_to(path);
		});
	}

	show() {
		const route = frappe.get_route();
		const route_path = route.length > 1 ? route.slice(1).join("/") : null;
		this.load_tree().then(() => {
			if (route_path === null) {
				if (!this.tree_data.length) {
					this.show_empty_state();
					return;
				}
				return this.select_first_page();
			}
			this.load_page(route_path);
		});
	}

	load_tree() {
		return frappe
			.xcall("frappe.desk.docs.get_tree")
			.then((tree) => {
				this.tree_data = tree || [];
				this.page_paths = this.collect_page_paths(this.tree_data);
				this.render_tree();
			})
			.catch(() => {
				this.tree_data = [];
				this.page_paths = new Set();
				this.render_tree();
			});
	}

	collect_page_paths(nodes) {
		const paths = new Set();
		for (const node of nodes) {
			if (node.has_page) {
				paths.add(node.path);
			}
			for (const child_path of this.collect_page_paths(node.children || [])) {
				paths.add(child_path);
			}
		}
		return paths;
	}

	render_tree() {
		this.$tree.empty();
		if (!this.tree_data.length) {
			return;
		}
		this.$tree.append(this.render_tree_nodes(this.tree_data));
	}

	render_tree_nodes(nodes) {
		const $list = $('<div class="docs-tree-list"></div>');
		for (const node of nodes) {
			const $item = $('<div class="docs-tree-item"></div>');
			const classes = ["docs-tree-node"];
			if (node.path === this.current_path) {
				classes.push("active");
			}
			$(
				`<a class="${classes.join(" ")}" data-path="${frappe.utils.escape_html(
					node.path
				)}" href="#">${frappe.utils.escape_html(node.title)}</a>`
			).appendTo($item);

			if (node.children?.length) {
				$item.append(
					$('<div class="docs-tree-children"></div>').append(
						this.render_tree_nodes(node.children)
					)
				);
			}
			$list.append($item);
		}
		return $list;
	}

	select_first_page() {
		return frappe.xcall("frappe.desk.docs.get_first_page").then((path) => {
			if (path === null || path === undefined) {
				this.show_empty_state();
				return;
			}
			if (path === "") {
				this.load_page("");
				return;
			}
			this.navigate_to(path, true);
		});
	}

	navigate_to(path, replace_route = false) {
		const route = ["docs"];
		if (path) {
			route.push(...path.split("/"));
		}
		if (replace_route) {
			frappe.set_route(route);
			return;
		}
		const current = frappe.get_route();
		if (current.slice(1).join("/") !== path) {
			frappe.set_route(route);
			return;
		}
		this.load_page(path);
	}

	load_page(path) {
		this.current_path = path;
		this.render_tree();
		this.show_loading();

		return frappe.call({
			method: "frappe.desk.docs.get_page",
			args: { path },
			callback: (response) => {
				this.show_page(response.message);
			},
			error: (response) => {
				this.show_error(response, path);
			},
		});
	}

	show_loading() {
		this.$state.addClass("hide");
		this.$reading.removeClass("hide").addClass("docs-loading").html("");
	}

	show_page(doc) {
		this.$reading.removeClass("docs-loading hide");
		this.$state.addClass("hide");
		this.page.set_title(doc.title || __("Documentation"));
		this.$reading.html(doc.content || "");
		this.update_breadcrumbs(doc.path, doc.title);
	}

	show_empty_state() {
		this.current_path = null;
		this.render_tree();
		this.$reading.addClass("hide");
		this.$state.removeClass("hide");
		this.$state_message.text(__("No documentation is available for your account."));
		this.update_breadcrumbs();
	}

	show_error(response, path) {
		this.$reading.addClass("hide").removeClass("docs-loading");
		this.$state.removeClass("hide");
		this.update_breadcrumbs(path);

		const exc_type = response?.exc_type || response?.responseJSON?.exc_type;
		if (exc_type === "PermissionError") {
			this.$state_message.text(__("Sorry! You are not permitted to view this page."));
			return;
		}

		if (exc_type === "DoesNotExistError") {
			this.$state_message.text(__("Sorry! I could not find what you were looking for."));
			return;
		}

		this.$state_message.text(
			__("Unable to load documentation page {0}", [path || __("Home")])
		);
	}

	find_path_trail(nodes, path, trail = []) {
		for (const node of nodes) {
			const next_trail = [...trail, node];
			if (node.path === path) {
				return next_trail;
			}
			const child_trail = this.find_path_trail(node.children || [], path, next_trail);
			if (child_trail) {
				return child_trail;
			}
		}
		return null;
	}

	get_docs_route(path) {
		return path ? `/desk/docs/${path}` : "/desk/docs";
	}

	update_breadcrumbs(path = null, title = null) {
		const items = [{ label: __("Documentation"), route: "/desk/docs" }];

		if (path === null || path === undefined) {
			frappe.breadcrumbs.add({ type: "Custom", items });
			return;
		}

		const trail = this.find_path_trail(this.tree_data, path);
		if (trail?.length) {
			for (const node of trail) {
				items.push({
					label: node.title,
					route: node.has_page ? this.get_docs_route(node.path) : "",
					disabled: !node.has_page,
				});
			}
		} else {
			this.append_path_segment_breadcrumbs(items, path, title);
		}

		frappe.breadcrumbs.add({ type: "Custom", items });
	}

	append_path_segment_breadcrumbs(items, path, title) {
		const segments = path.split("/");
		let accumulated = "";

		for (let index = 0; index < segments.length; index++) {
			accumulated = accumulated ? `${accumulated}/${segments[index]}` : segments[index];
			const is_last = index === segments.length - 1;
			const node = this.find_tree_node(this.tree_data, accumulated);

			items.push({
				label:
					is_last && title
						? title
						: node?.title ||
						  frappe.utils.to_title_case(segments[index].replace(/-/g, " ")),
				route: !is_last && node?.has_page ? this.get_docs_route(accumulated) : "",
				disabled: is_last || !node?.has_page,
			});
		}
	}

	find_tree_node(nodes, path) {
		for (const node of nodes) {
			if (node.path === path) {
				return node;
			}
			const child = this.find_tree_node(node.children || [], path);
			if (child) {
				return child;
			}
		}
		return null;
	}
};
