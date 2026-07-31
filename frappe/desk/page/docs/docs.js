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
		this.current_locale = frappe.boot.lang || "en";
		this.locales = [];
		this.setup_layout();
	}

	setup_layout() {
		this.$sidebar = $('<div class="docs-sidebar"></div>').appendTo(this.page.sidebar);
		this.$tree = $('<div class="docs-tree"></div>').appendTo(this.$sidebar);
		this.$locale_picker = $(`
			<div class="docs-locale-picker">
				<label class="docs-locale-label" for="docs-locale-select">${__("Language")}</label>
				<select id="docs-locale-select" class="form-control docs-locale-select"></select>
			</div>
		`).appendTo(this.$sidebar);
		this.$locale_select = this.$locale_picker.find(".docs-locale-select");
		this.$locale_select.on("change", () => {
			this.switch_locale(this.$locale_select.val());
		});
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
		this.ensure_locales().then(() => {
			const parsed = this.parse_route(route);
			if (!parsed.locale) {
				return this.resolve_and_redirect(parsed.path);
			}
			this.current_locale = parsed.locale;
			this.load_tree().then(() => {
				this.update_locale_picker();
				if (parsed.path === null) {
					if (!this.tree_data.length) {
						this.show_empty_state();
						return;
					}
					return this.select_first_page();
				}
				this.load_page(parsed.path);
			});
		});
	}

	ensure_locales() {
		if (this.locales.length) {
			return Promise.resolve(this.locales);
		}
		return frappe.xcall("frappe.desk.docs.get_locales").then((locales) => {
			this.locales = (locales || []).map((locale) =>
				typeof locale === "string" ? { locale, label: locale } : locale
			);
		});
	}

	get_locale_codes() {
		return this.locales.map((locale) => locale.locale);
	}

	render_locale_picker(variants = []) {
		const options = variants.length ? variants : this.locales;
		const current = this.$locale_select.val();

		this.$locale_picker.toggleClass("hide", options.length <= 1);
		this.$locale_select.empty();

		for (const option of options) {
			const locale = option.locale;
			const label = option.label || locale;
			this.$locale_select.append($("<option></option>").attr("value", locale).text(label));
		}

		if (options.some((option) => option.locale === this.current_locale)) {
			this.$locale_select.val(this.current_locale);
		} else if (current) {
			this.$locale_select.val(current);
		}
	}

	update_locale_picker() {
		if (!this.locales.length) {
			return Promise.resolve();
		}

		return frappe
			.xcall("frappe.desk.docs.get_page_variants", { path: this.current_path || "" })
			.then((variants) => {
				this.render_locale_picker(variants || []);
			})
			.catch(() => {
				this.render_locale_picker(this.locales);
			});
	}

	switch_locale(locale) {
		if (!locale || locale === this.current_locale) {
			return;
		}

		const path = this.current_path || "";
		const route = ["docs", locale];
		if (path) {
			route.push(...path.split("/"));
		}

		frappe
			.xcall("frappe.desk.docs.get_page", { path, locale })
			.then(() => frappe.set_route(route))
			.catch(() => {
				frappe.xcall("frappe.desk.docs.get_first_page", { locale }).then((first_path) => {
					const fallback = ["docs", locale];
					if (first_path) {
						fallback.push(...first_path.split("/"));
					}
					frappe.set_route(fallback);
				});
			});
	}

	parse_route(route) {
		const segments = route.slice(1);
		if (segments.length && this.is_locale_segment(segments[0])) {
			return {
				locale: segments[0],
				path: segments.length > 1 ? segments.slice(1).join("/") : null,
			};
		}
		return {
			locale: null,
			path: segments.length ? segments.join("/") : null,
		};
	}

	is_locale_segment(segment) {
		const locale_codes = this.get_locale_codes();
		if (locale_codes.includes(segment)) {
			return true;
		}
		const parent = segment.split("-")[0];
		return parent !== segment && locale_codes.includes(parent);
	}

	resolve_and_redirect(path) {
		return frappe
			.xcall("frappe.desk.docs.resolve_locale", { path: path || "" })
			.then((result) => {
				const route = ["docs", result.locale];
				if (result.path) {
					route.push(...result.path.split("/"));
				}
				frappe.set_route(route);
			});
	}

	load_tree() {
		return frappe
			.xcall("frappe.desk.docs.get_tree", { locale: this.current_locale })
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
		return frappe
			.xcall("frappe.desk.docs.get_first_page", { locale: this.current_locale })
			.then((path) => {
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
		const route = ["docs", this.current_locale];
		if (path) {
			route.push(...path.split("/"));
		}
		if (replace_route) {
			frappe.set_route(route);
			return;
		}
		const current = frappe.get_route();
		const current_path = current.slice(2).join("/");
		if (current[1] !== this.current_locale || current_path !== path) {
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
			args: { path, locale: this.current_locale },
			callback: (response) => {
				if (response.exc_type) {
					this.show_error(response, path);
					return;
				}
				this.show_page(response.message);
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
		this.update_locale_picker();
	}

	show_empty_state() {
		this.current_path = null;
		this.render_tree();
		this.$reading.addClass("hide");
		this.$state.removeClass("hide");
		this.$state_message.text(__("No documentation is available for your account."));
		this.update_breadcrumbs();
		this.update_locale_picker();
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
		const route = `/desk/docs/${this.current_locale}`;
		return path ? `${route}/${path}` : route;
	}

	update_breadcrumbs(path = null, title = null) {
		const items = [{ label: __("Documentation"), route: this.get_docs_route() }];

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
