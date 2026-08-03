// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

/**
 * Make a standard page layout with a toolbar and title
 *
 * @param {Object} opts
 *
 * @param {string} opts.parent [HTMLElement] Parent element
 * @param {boolean} opts.single_column Whether to include sidebar
 * @param {string} [opts.sidebar_position] Position of sidebar (default None, "Left" or "Right")
 * @param {string} [opts.title] Page title
 * @param {Object} [opts.make_page]
 *
 * @returns {frappe.ui.Page}
 */

/**
 * @typedef {Object} frappe.ui.Page
 */

frappe.ui.make_app_page = function (opts) {
	opts.parent.page = new frappe.ui.Page(opts);
	// A page is usually built before the container switches to it, but not always: a form creates
	// its frappe.ui.Page inside the first frm.refresh(), by which point change_to() has already
	// pointed the container at this element. Sidebar visibility was therefore resolved against a
	// page that carried no options yet and fell back to hidden. Re-resolve now that they exist.
	if (frappe.container?.page === opts.parent) {
		frappe.app.sidebar.apply_page_visibility();
	}
	return opts.parent.page;
};

frappe.ui.pages = {};

// bootstrap button types (the public add_inner_button/add_button vocabulary)
// mapped onto the es-button contract; unknown types fall back to subtle
const BTN_TYPE_TO_ES = {
	default: { variant: "subtle" },
	secondary: { variant: "subtle" },
	light: { variant: "subtle" },
	primary: { variant: "solid" },
	danger: { variant: "solid", theme: "red" },
	ghost: { variant: "ghost" },
};

function es_opts_for_btn_type(type) {
	return BTN_TYPE_TO_ES[type] || BTN_TYPE_TO_ES.default;
}

frappe.ui.Page = class Page {
	constructor(opts) {
		$.extend(this, opts);

		this.set_document_title = true;
		this.buttons = {};
		this.fields_dict = {};
		this.views = {};

		this.make();
		if (!Object.keys(opts).includes("hide_sidebar")) this.hide_sidebar = false;
		// pages can hide just the workspace dock (while keeping the body sidebar) via this option;
		// a page that hides the whole sidebar hides the dock too (see Sidebar.page_allows_dock)
		if (!Object.keys(opts).includes("hide_workspace_dock")) this.hide_workspace_dock = false;
		frappe.ui.pages[frappe.get_route_str()] = this;
	}

	make() {
		this.wrapper = $(this.parent);
		this.add_main_section();
		this.setup_main_sidebar_toggle();
		this.setup_awesomebar();
	}

	setup_awesomebar() {
		if (frappe.boot.desk_settings.search_bar && !frappe.app.awesome_bar) {
			let awesome_bar = new frappe.search.AwesomeBar();
			awesome_bar.setup(".navbar-modal-search-mobile");
			frappe.app.awesome_bar = awesome_bar;
			frappe.search.utils.make_function_searchable(
				frappe.utils.generate_tracking_url,
				__("Generate Tracking URL")
			);
			if (frappe.model.can_read("RQ Job")) {
				frappe.search.utils.make_function_searchable(function () {
					frappe.set_route("List", "RQ Job");
				}, __("Background Jobs"));
			}
		}
	}

	get_empty_state(title, message, primary_action) {
		return $(`<div class="page-card-container">
  			<div class="page-card">
  				<div class="page-card-head">
  					<span class="indicator blue">
  						${title}</span>
  				</div>
  				<p>${message}</p>
  				<div>
  					<button class="btn btn-primary btn-sm">${primary_action}</button>
  				</div>
  			</div>
  		</div>`);
	}

	load_lib(callback) {
		frappe.require(this.required_libs, callback);
	}

	add_main_section() {
		$(frappe.render_template("page", {})).appendTo(this.wrapper);
		if (this.single_column) {
			// nesting under col-sm-12 for consistency
			this.add_view(
				"main",
				'<div class="layout-main">\
					<div class="layout-main-section-wrapper">\
						<div class="layout-main-section"></div>\
						<div class="layout-footer hide"></div>\
					</div>\
				</div>'
			);
		} else {
			this.add_view(
				"main",
				`
				<div class="layout-main layout-two-column">
					<div class="layout-side-section"></div>
					<div class="layout-main-section-wrapper">
						<div class="layout-main-section"></div>
						<div class="layout-footer hide"></div>
					</div>
				</div>
			`
			);

			if (this.sidebar_position === "Right") {
				this.wrapper
					.find(".layout-main-section-wrapper")
					.insertBefore(this.wrapper.find(".layout-side-section"));
				this.wrapper.find(".layout-side-section").addClass("right");
			}
		}

		this.setup_page();
	}

	setup_page() {
		this.$title_area = this.wrapper.find(".title-area");

		this.$sub_title_area = this.wrapper.find("h6");

		if (this.title) this.set_title(this.title);

		if (this.icon) this.get_main_icon(this.icon);

		this.body = this.main = this.wrapper.find(".layout-main-section");
		this.container = this.wrapper.find(".page-body");
		this.sidebar = this.wrapper.find(".layout-side-section");
		this.footer = this.wrapper.find(".layout-footer");
		this.indicator = this.wrapper.find(".title-area .page-indicator-pill");

		this.page_actions = this.wrapper.find(".page-actions");
		this.filters = this.wrapper.find(".filters");
		this.page_head = this.wrapper.find(".page-head");
		this.btn_primary = this.page_actions.find(".primary-action");
		this.btn_secondary = this.page_actions.find(".secondary-action");

		this.menu = this.page_actions.find(".menu-btn-group .dropdown-menu");
		this.menu_btn_group = this.page_actions.find(".menu-btn-group");

		this.actions = this.page_actions.find(".actions-btn-group .dropdown-menu");
		this.actions_btn_group = this.page_actions.find(".actions-btn-group");

		this.standard_actions = this.page_actions.find(".standard-actions");
		this.custom_actions = this.page_actions.find(".custom-actions");
		this.custom_mobile_actions = this.page_actions.find(".custom-mobile-actions");

		this.page_form = $('<div class="page-form row hide"></div>').prependTo(this.main);
		this.inner_toolbar = this.custom_actions;
		this.icon_group = this.page_actions.find(".page-icon-group");

		if (this.make_page) {
			this.make_page();
		}

		// keyboard shortcuts
		let menu_btn = this.menu_btn_group.find("button");
		menu_btn
			.attr("title", __("Menu"))
			.tooltip({ delay: { show: 600, hide: 100 } })
			.on("click mousedown", function () {
				$(this).tooltip("hide");
			});
		frappe.ui.keys.get_shortcut_group(this.page_actions[0]).add(menu_btn);

		// The Menu / Actions dropdowns are espresso menus. The old bootstrap
		// ULs stay in the DOM as hidden item stores: add_dropdown_item keeps
		// writing <li><a> markup there (the returned jQuery is public API and
		// callers mutate it), and every open snapshots the store into rows —
		// so .text() / .toggle() / .addClass("disabled") all keep working.
		this.menu_dropdown = new frappe.ui.Dropdown({
			trigger: menu_btn,
			align: "end",
			options: () => this.build_dropdown_options(this.menu),
		});
		this.actions_dropdown = new frappe.ui.Dropdown({
			trigger: this.actions_btn_group.find("button"),
			align: "end",
			options: () => this.build_dropdown_options(this.actions),
		});
		// the menus body-portal, so one left open would float over the next
		// page — the container fires "hide" on the page element on switch
		this.wrapper.on("hide", () => {
			this.menu_dropdown.close("owner");
			this.actions_dropdown.close("owner");
			this.wrapper.find(".inner-group-button, .custom-btn-group").each((_, group) => {
				$(group).data("es_dropdown")?.close("owner");
			});
		});

		// desktop shows "Actions" + chevron; mobile keeps just the chevron.
		// actions-btn-group-label stays as the legacy hook name for the span.
		let action_btn = this.actions_btn_group.find("button");
		let action_btn_label = action_btn
			.find(".es-button__label")
			.addClass("hidden-xs actions-btn-group-label");
		frappe.ui.keys.get_shortcut_group(this.page_actions[0]).add(action_btn, action_btn_label);

		// https://axesslab.com/skip-links
		this.skip_link_to_main = $("<button>")
			.addClass("sr-only sr-only-focusable btn btn-primary-light my-2")
			.text(__("Navigate to main content"))
			.attr({ tabindex: 0, role: "link" })
			.on("click", (e) => {
				e.preventDefault();
				const main = this.main.get(0);
				main.setAttribute("tabindex", -1);
				main.focus();
				main.addEventListener(
					"blur",
					() => {
						main.removeAttribute("tabindex");
					},
					{ once: true }
				);
			})
			.appendTo(this.sidebar);
	}

	set_indicator(label, color) {
		let indicator_html = `<span>${label}</span>`;
		const is_mobile = frappe.is_mobile();
		if (is_mobile) {
			indicator_html = `<span class="indicator-doc-html" style="background-color: var(--${color}-400)"></span>`;
		}
		this.clear_indicator().removeClass("hide").html(indicator_html).attr("data-theme", color);

		if (is_mobile) {
			this.indicator.attr("title", label);
			this.indicator.tooltip();
		}
	}

	add_action_icon(icon, click, css_class = "", tooltip_label) {
		const button = $(`
			<button class="text-muted btn btn-default ${css_class} icon-btn">
				${frappe.utils.icon(icon)}
			</button>
		`);
		// ideally, we should pass tooltip_label this is just safe gaurd.
		if (!tooltip_label) {
			tooltip_label = frappe.unscrub(icon);
		}

		button.appendTo(this.icon_group.removeClass("hide"));
		button.click(click);
		button
			.attr("title", __(tooltip_label))
			.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });

		return button;
	}

	setup_main_sidebar_toggle() {
		this.wrapper.find(".sidebar-toggle-btn.navbar-brand").on("click", (event) => {
			frappe.app.sidebar.set_height();
			frappe.app.sidebar.toggle_width();
			frappe.app.sidebar.prevent_scroll();
		});
	}

	clear_indicator() {
		return this.indicator
			.removeClass()
			.removeAttr("data-theme")
			.addClass("es-badge page-indicator-pill hide");
	}

	get_icon_label(icon, label) {
		let icon_name = icon;
		let size = "xs";
		if (typeof icon === "object") {
			icon_name = icon.icon;
			size = icon.size || "xs";
		}
		return `${icon ? frappe.utils.icon(icon_name, size) : ""} <span class="hidden-xs"> ${__(
			label
		)} </span>`;
	}

	set_action(btn, opts) {
		let me = this;

		this.clear_action_of(btn);

		// icon can be a name or { icon, size } — the es contract sizes icons
		// from the button itself, so only the name matters now. Guard against
		// null: callers pass it to skip the icon (typeof null === "object")
		const icon = opts.icon && typeof opts.icon === "object" ? opts.icon.icon : opts.icon;
		const dress_opts = {
			label: opts.label,
			icon: icon,
			variant: opts.variant,
		};
		// only pass loading_label through when the caller gave one, so the
		// component's default map (Save → Saving...) still applies otherwise
		if (opts.working_label) {
			dress_opts.loading_label = opts.working_label;
		}
		frappe.ui.button.dress(btn, dress_opts);

		btn.removeClass("hide")
			.prop("disabled", false)
			.attr("data-label", opts.label)
			.on("click", function () {
				// busy blocks the mouse via pointer-events, but keyboard
				// activation still fires — guard re-entry
				if (btn.attr("aria-busy") === "true") return;
				let response = opts.click.apply(this, [btn]);
				me.btn_disable_enable(btn, response);
			});

		if (opts.short_label) {
			// responsive label pair: the full label shows from md up, the short
			// one below md (hidden-xs and hidden-lg are exact complements at
			// the 768px boundary) — CSS decides, so resizing just works
			btn.find(".es-button__label").addClass("hidden-xs");
			$('<span class="es-button__label hidden-lg"></span>')
				.text(opts.short_label)
				.insertAfter(btn.find(".es-button__label").first());
		} else if (opts.icon) {
			// with an icon and no short label, mobile shows the icon alone
			// (page.scss squares the button into an icon button below md)
			btn.find(".es-button__label").addClass("hidden-xs");
		}

		if (opts.working_label) {
			btn.attr("data-working-label", opts.working_label);
		}

		// alt shortcuts — pass the full label span alone; the button also
		// contains the spinner, loading-label and short-label spans, whose
		// text must not join in
		let text_span = btn.find(".es-button__label").first();
		frappe.ui.keys.get_shortcut_group(this).add(btn, text_span.length ? text_span : btn);
	}

	// `label` can be a plain string, or { label, short_label } to show a
	// shorter text below the md breakpoint (e.g. "Add" for "Add Sales Order")
	set_primary_action(label, click, icon, working_label) {
		this.set_action(this.btn_primary, {
			...(label && typeof label === "object" ? label : { label }),
			click: click,
			icon: icon,
			working_label: working_label,
			variant: "solid",
		});
		return this.btn_primary;
	}

	set_secondary_action(label, click, icon, working_label) {
		this.set_action(this.btn_secondary, {
			...(label && typeof label === "object" ? label : { label }),
			click: click,
			icon: icon,
			working_label: working_label,
			variant: "subtle",
		});

		return this.btn_secondary;
	}

	clear_action_of(btn) {
		btn.addClass("hide").unbind("click").removeAttr("data-working-label");
	}

	clear_primary_action() {
		this.clear_action_of(this.btn_primary);
	}

	clear_secondary_action() {
		this.clear_action_of(this.btn_secondary);
	}

	clear_actions() {
		this.clear_primary_action();
		this.clear_secondary_action();
	}

	// Close and tear down the espresso dropdowns of button groups inside
	// $scope before their elements are discarded — an open menu body-portals,
	// so removing its group would otherwise leave the panel floating over
	// the page with its listeners live.
	destroy_group_dropdowns($scope) {
		$scope
			.find(".inner-group-button, .custom-btn-group")
			.addBack(".inner-group-button, .custom-btn-group")
			.each((_, group) => {
				$(group).data("es_dropdown")?.destroy();
			});
	}

	clear_custom_actions() {
		this.destroy_group_dropdowns(this.custom_actions);
		this.custom_actions.addClass("hide").empty();
		this.clear_mobile_custom_groups();
	}
	clear_mobile_custom_groups() {
		const $groups = this.custom_mobile_actions.children(
			".custom-btn-group:not(.view-switcher)"
		);
		this.destroy_group_dropdowns($groups);
		$groups.remove();
	}

	clear_icons() {
		this.icon_group.addClass("hide").empty();
	}

	//--- Menu --//

	add_menu_item(label, click, standard, shortcut, show_parent) {
		return this.add_dropdown_item({
			label,
			click,
			standard,
			parent: this.menu,
			shortcut,
			show_parent,
		});
	}

	add_custom_menu_item(parent, label, click, standard, shortcut, icon = null) {
		return this.add_dropdown_item({
			label,
			click,
			standard,
			parent: parent,
			shortcut,
			icon,
		});
	}

	clear_menu() {
		this.clear_btn_group(this.menu);
	}

	show_menu() {
		this.menu_btn_group.removeClass("hide");
	}

	hide_menu() {
		this.menu_btn_group.addClass("hide");
	}

	show_icon_group() {
		this.icon_group.removeClass("hide");
	}

	hide_icon_group() {
		this.icon_group.addClass("hide");
	}

	//--- Actions Menu--//

	show_actions_menu() {
		this.actions_btn_group.removeClass("hide");
	}

	hide_actions_menu() {
		this.actions_btn_group.addClass("hide");
	}

	add_action_item(label, click, standard) {
		return this.add_dropdown_item({
			label,
			click,
			standard,
			parent: this.actions,
		});
	}

	add_actions_menu_item(label, click, standard, shortcut) {
		return this.add_dropdown_item({
			label,
			click,
			standard,
			shortcut,
			parent: this.actions,
			show_parent: false,
		});
	}

	clear_actions_menu() {
		this.clear_btn_group(this.actions);
	}

	//-- Generic --//

	/*
	 * Add label to given drop down menu. If label, is already contained in the drop
	 * down menu, it will be ignored.
	 * @param {string} label - Text for the drop down menu
	 * @param {function} click - function to be called when `label` is clicked
	 * @param {Boolean} standard
	 * @param {object} parent - DOM object representing the parent of the drop down item lists
	 * @param {string} shortcut - Keyboard shortcut associated with the element
	 * @param {Boolean} show_parent - Whether to show the dropdown button if dropdown item is added
	 */
	add_dropdown_item({
		label,
		click,
		standard,
		parent,
		shortcut,
		show_parent = true,
		icon = null,
	}) {
		if (show_parent) {
			parent.parent().removeClass("hide hidden-xl");
		}

		let $link = this.is_in_group_button_dropdown(parent, "li > a.grey-link > span", label);
		if ($link) return $link;

		let $li;
		let $icon = ``;

		if (icon) {
			$icon = `<span class="menu-item-icon flex align-items-center justify-items-center">${frappe.utils.icon(
				icon
			)}</span>`;
		}

		const data_label = encodeURIComponent(label);
		if (shortcut) {
			let shortcut_obj = this.prepare_shortcut_obj(shortcut, click, label);
			$li = $(`
				<li>
					<a class="grey-link dropdown-item" href="#" onClick="return false;">
						${$icon}
						<span class="menu-item-label" data-label="${data_label}">${label}</span>
						<span class="menu-item-shortcut">${shortcut_obj.shortcut_label}</span>
					</a>
				</li>
			`);
			// binding stays here — the menu rows only display the combo
			frappe.ui.keys.add_shortcut(shortcut_obj);
			$li.data("menu_shortcut", shortcut_obj.shortcut);
		} else {
			$li = $(`
				<li>
					<a class="grey-link dropdown-item" href="#" onClick="return false;">
						${$icon}
						<span class="menu-item-label" data-label="${data_label}">${label}</span>
					</a>
				</li>
			`);
		}

		// the snapshot (build_dropdown_options) reads these back
		$li.data("menu_click", click);
		if (icon) $li.data("menu_icon", icon);

		$link = $li.find("a").on("click", (e) => {
			if (e.ctrlKey || e.metaKey) {
				frappe.open_in_new_tab = true;
			}
			return click();
		});

		if (standard) {
			$li.appendTo(parent);
		} else {
			this.divider = parent.find(".dropdown-divider.user-action");
			if (!this.divider.length) {
				this.divider = $(
					'<li class="dropdown-divider user-action visible-xs"></li>'
				).prependTo(parent);
			}
			$li.addClass("user-action").insertBefore(this.divider);
		}

		return $link;
	}

	// Snapshot a hidden item store (this.menu / this.actions) into menu rows.
	// Reading the live elements on every open is what keeps the legacy jQuery
	// contract alive: .text(), .toggle(), .addClass("disabled") on a held item
	// all show up the next time the menu opens. Divider <li>s split groups.
	build_dropdown_options($parent) {
		// classes internal to the legacy markup; everything else (visible-xs,
		// hidden-xl, caller classes) is carried onto the rendered row
		const internal = ["grey-link", "dropdown-item", "disabled", "user-action"];
		// the responsive utilities, evaluated at open time — a group whose
		// rows are all CSS-hidden would still paint its separator, and the
		// legacy divider was itself visible-xs (desktop menus had none)
		const responsive_hidden = (el) =>
			(el.classList.contains("visible-xs") &&
				window.matchMedia("(min-width: 576px)").matches) ||
			(el.classList.contains("hidden-xl") &&
				window.matchMedia("(min-width: 992px)").matches);
		const segments = [[]];
		// one submenu row per inner-button group, keyed by group label
		const nested_groups = new Map();

		$parent.children("li").each((_, li) => {
			if (li.classList.contains("dropdown-divider")) {
				if (!responsive_hidden(li) && segments[segments.length - 1].length) {
					segments.push([]);
				}
				return;
			}
			const $li = $(li);
			const a = $li.children("a").get(0);
			if (!a) return;
			// .toggle(false) / .hide() by callers
			if (li.style.display === "none" || a.style.display === "none") return;
			if (responsive_hidden(li) || responsive_hidden(a)) return;

			// .text(label) on the held <a> replaces its children, so fall back
			const label = ($li.find(".menu-item-label").text() || $(a).text()).trim();
			if (!label) return;

			const css_class = [...li.classList, ...a.classList]
				.filter((c) => !internal.includes(c))
				.join(" ");
			const click = $li.data("menu_click");
			const onclick = (e) => {
				if (e && (e.ctrlKey || e.metaKey)) {
					frappe.open_in_new_tab = true;
				}
				// raw <li>s appended by apps have no stashed handler —
				// clicking their own link keeps them working
				return click ? click() : a.click();
			};

			// grouped inner buttons mirror into this menu on mobile as flat
			// "Group > Label" store items (see add_inner_button) — render
			// them as one "Group" row with a submenu instead
			const nested = $li.data("menu_submenu");
			if (nested) {
				let submenu = nested_groups.get(nested.group);
				if (!submenu) {
					submenu = [];
					nested_groups.set(nested.group, submenu);
					segments[segments.length - 1].push({
						label: nested.group,
						css_class: css_class || undefined,
						submenu,
					});
				}
				submenu.push({
					label: nested.label,
					disabled: a.classList.contains("disabled"),
					onclick,
				});
				return;
			}

			segments[segments.length - 1].push({
				label,
				icon: $li.data("menu_icon") || undefined,
				shortcut: $li.data("menu_shortcut") || undefined,
				disabled: a.classList.contains("disabled"),
				css_class: css_class || undefined,
				onclick,
			});
		});

		const groups = segments.filter((segment) => segment.length);
		if (groups.length <= 1) return groups[0] || [];
		return groups.map((options) => ({ group: "", hide_label: true, options }));
	}

	prepare_shortcut_obj(shortcut, click, label) {
		let shortcut_obj;
		// convert to object, if shortcut string passed
		if (typeof shortcut === "string") {
			shortcut_obj = { shortcut };
		} else {
			shortcut_obj = shortcut;
		}
		shortcut_obj.shortcut_label = frappe.ui.keys.get_shortcut_label(shortcut_obj.shortcut);

		// actual shortcut string
		shortcut_obj.shortcut = shortcut_obj.shortcut.toLowerCase();
		// action is button click
		if (!shortcut_obj.action) {
			shortcut_obj.action = click;
		}
		// shortcut description can be button label
		if (!shortcut_obj.description) {
			shortcut_obj.description = label;
		}
		// page
		shortcut_obj.page = this;
		return shortcut_obj;
	}

	/*
	 * Check if there already exists a button with a specified label in a specified button group
	 * @param {object} parent - This should be the `ul` of the button group.
	 * @param {string} selector - CSS Selector of the button to be searched for. By default, it is `li`.
	 * @param {string} label - Label of the button
	 */
	is_in_group_button_dropdown(parent, selector, label) {
		if (!selector) selector = "li";

		if (!label || !parent) return false;

		const item_selector = `${selector}[data-label="${encodeURIComponent(label)}"]`;

		const existing_items = $(parent).find(item_selector);
		return existing_items?.length > 0 && existing_items;
	}

	clear_btn_group(parent) {
		// a refresh can clear the store while its menu is open — close it so
		// the portaled panel doesn't float on with stale rows
		if (parent.is(this.menu)) this.menu_dropdown?.close("owner");
		if (parent.is(this.actions)) this.actions_dropdown?.close("owner");
		parent.empty();
		parent.parent().addClass("hide");
	}

	add_divider() {
		return $('<li class="dropdown-divider"></li>').appendTo(this.menu);
	}

	get_or_add_inner_group_button(label, align_right) {
		var $group = this.inner_toolbar.find(
			`.inner-group-button[data-label="${encodeURIComponent(label)}"]`
		);
		if (!$group.length) {
			// same bridge as the header menus: the .dropdown-menu div stays in
			// the DOM as a hidden item store (add_inner_button returns its
			// <a>s to callers, who mutate them), and the espresso dropdown
			// snapshots it on every open
			$group = $(
				`<div class="inner-group-button" data-label="${encodeURIComponent(label)}">
					<div role="presentation" class="dropdown-menu ${align_right ? "dropdown-menu-right" : ""}"></div>
				</div>`
			).appendTo(this.inner_toolbar);
			const $btn = frappe.ui
				.button({
					label: label,
					icon_right: "chevrons-up-down",
					css_class: "ellipsis",
				})
				.prependTo($group);
			$group.data(
				"es_dropdown",
				new frappe.ui.Dropdown({
					trigger: $btn,
					align: align_right ? "end" : "start",
					options: () =>
						this.build_inner_group_options($group.children(".dropdown-menu")),
				})
			);
		}
		return $group;
	}

	// Snapshot an inner group's item store — bare <a.dropdown-item> children
	// plus divider <li>s — into menu rows; same live-read contract as
	// build_dropdown_options, so held-reference mutations show on next open.
	build_inner_group_options($store) {
		const segments = [[]];
		$store.children().each((_, el) => {
			if (el.classList.contains("dropdown-divider")) {
				if (segments[segments.length - 1].length) segments.push([]);
				return;
			}
			// match by tag, not .dropdown-item — change_inner_button_type's
			// legacy removeClass() strips ALL classes off the store item
			if (el.tagName !== "A" || el.style.display === "none") return;
			const label = $(el).text().trim();
			if (!label) return;
			const internal = ["dropdown-item", "disabled", "btn", "btn-danger", "text-danger"];
			const css_class = [...el.classList].filter((c) => !internal.includes(c)).join(" ");
			segments[segments.length - 1].push({
				label,
				disabled: el.classList.contains("disabled"),
				// btn-danger comes from change_inner_button_type(label, group,
				// "danger"); text-danger is how apps mark risky rows
				theme:
					el.classList.contains("btn-danger") || el.classList.contains("text-danger")
						? "red"
						: undefined,
				css_class: css_class || undefined,
				// clicking the store element runs every handler callers bound
				onclick: () => $(el).trigger("click"),
			});
		});
		const groups = segments.filter((segment) => segment.length);
		if (groups.length <= 1) return groups[0] || [];
		return groups.map((options) => ({ group: "", hide_label: true, options }));
	}

	get_inner_group_button(label) {
		return this.inner_toolbar.find(
			`.inner-group-button[data-label="${encodeURIComponent(label)}"]`
		);
	}

	set_inner_btn_group_as_primary(label) {
		const group = this.get_or_add_inner_group_button(label);
		const dropdown_items = group.find(".dropdown-menu .dropdown-item");

		if (dropdown_items.length > 0) {
			group.find("button").attr("data-variant", "solid");
		} else {
			group.toggleClass("hide", true);
		}
	}

	btn_disable_enable(btn, response) {
		// aria-busy, not disabled: disabling ejects keyboard focus, busy shows
		// the es-button spinner/loading-label and blocks clicks. Direct
		// .prop("disabled") pokes from outside still work (es-button styles
		// :disabled) — this only changes what the page does on its own.
		const busy = (on) => (on ? btn.attr("aria-busy", "true") : btn.removeAttr("aria-busy"));
		if (response && response.then) {
			busy(true);
			response.finally(() => busy(false));
		} else if (response && response.always) {
			busy(true);
			response.always(() => busy(false));
		}
	}
	add_divider_to_button_group(group) {
		var $group = this.get_or_add_inner_group_button(group);
		$('<li class="dropdown-divider"></li>').appendTo($group.find(".dropdown-menu"));
	}
	/*
	 * Add button to button group. If there exists another button with the same label,
	 * `add_inner_button` will not add the new button to the button group even if the callback
	 * function is different.
	 *
	 * @param {string} label - Label of the button to be added to the group
	 * @param {object} action - function to be called when button is clicked
	 * @param {string} group - Label of the group button
	 */
	add_inner_button(label, action, group, type = "default", align_right = false) {
		var me = this;
		let _action = function () {
			let btn = $(this);
			let response = action();
			me.btn_disable_enable(btn, response);
		};

		// Add actions as menu item in Mobile View. The store keeps the flat
		// "Group > Label" item (dedupe and remove_custom_button look it up by
		// that label) — the snapshot renders stamped items as a nested
		// "Group" row with a submenu instead.
		let menu_item_label = group ? `${group} > ${label}` : label;
		let menu_item = this.add_menu_item(menu_item_label, _action, false, false, false);
		if (group) {
			menu_item.closest("li").data("menu_submenu", { group, label });
		}
		menu_item.parent().addClass("hidden-xl");
		if (this.menu_btn_group.hasClass("hide")) {
			this.menu_btn_group.removeClass("hide").addClass("hidden-xl");
		}

		if (group) {
			var $group = this.get_or_add_inner_group_button(group, align_right);
			$(this.inner_toolbar).removeClass("hide");

			if (!this.is_in_group_button_dropdown($group.find(".dropdown-menu"), "a", label)) {
				return $(
					`<a class="dropdown-item" href="#" onclick="return false;" data-label="${encodeURIComponent(
						label
					)}">${label}</a>`
				)
					.on("click", _action)
					.appendTo($group.find(".dropdown-menu"));
			}
		} else {
			let button = this.inner_toolbar.find(
				`button[data-label="${encodeURIComponent(label)}"]`
			);
			if (button.length == 0) {
				button = frappe.ui.button({
					label: __(label),
					...es_opts_for_btn_type(type),
					css_class: "ellipsis",
					attrs: { "data-label": encodeURIComponent(label) },
				});
				button.on("click", _action);
				button.appendTo(this.inner_toolbar.removeClass("hide"));
			}
			return button;
		}
	}

	remove_inner_button(label, group) {
		if (typeof label === "string") {
			label = [label];
		}
		// translate
		label = label.map((l) => __(l));

		if (group) {
			var $group = this.get_inner_group_button(__(group));
			if ($group.length) {
				$group.find(`.dropdown-item[data-label="${encodeURIComponent(label)}"]`).remove();
			}
			if ($group.find(".dropdown-item").length === 0) {
				this.destroy_group_dropdowns($group);
				$group.remove();
			}
		} else {
			this.inner_toolbar.find(`button[data-label="${encodeURIComponent(label)}"]`).remove();
		}
	}

	change_inner_button_type(label, group, type) {
		let btn;

		if (group) {
			// the class poke lands on the store item; the snapshot maps
			// btn-danger to the red row theme. Strips extra classes
			// (pre-existing behavior).
			var $group = this.get_inner_group_button(__(group));
			if ($group.length) {
				btn = $group.find(`.dropdown-item[data-label="${encodeURIComponent(label)}"]`);
				if (btn) btn.removeClass().addClass(`btn btn-${type} ellipsis`);
			}
		} else {
			// es-buttons change look via data attributes — the classes
			// (es-button, ellipsis, data-label hooks) must survive
			btn = this.inner_toolbar.find(`button[data-label="${encodeURIComponent(label)}"]`);
			if (btn.length) {
				const es = es_opts_for_btn_type(type);
				// defaults (subtle/gray) are expressed by NO attribute
				es.variant === "subtle"
					? btn.removeAttr("data-variant")
					: btn.attr("data-variant", es.variant);
				es.theme ? btn.attr("data-theme", es.theme) : btn.removeAttr("data-theme");
			}
		}
	}

	add_inner_message(message) {
		let $message = $(`<span class='inner-page-message text-muted small'>${message}</div>`);
		this.inner_toolbar.find(".inner-page-message").remove();
		this.inner_toolbar.removeClass("hide").prepend($message);

		return $message;
	}

	clear_inner_toolbar() {
		// inner_toolbar IS custom_actions (see setup_page) — delegate so the
		// dropdown teardown and the mobile-container clear live in one place
		this.clear_custom_actions();
	}

	clear_user_actions() {
		this.menu.find(".user-action").remove();
	}

	// page::title
	get_title_area() {
		return this.$title_area;
	}

	set_title(title, icon = null, strip = true, tab_title = "", tooltip_label = "") {
		if (!title) title = "";
		if (strip) {
			title = strip_html(title);
		}
		this.title = title;
		frappe.utils.set_title(tab_title || title);
		if (icon) {
			title = `${frappe.utils.icon(icon)} ${title}`;
		}

		let title_wrapper = this.$title_area.find(".title-text");
		title_wrapper.html(title);
		title_wrapper.attr("title", __(tooltip_label) || this.title);

		if (tooltip_label) {
			title_wrapper.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });
		}
	}

	set_title_sub(txt) {
		// strip icon
		this.$sub_title_area.html(txt).toggleClass("hide", !!!txt);
	}

	get_main_icon(icon) {
		return this.$title_area.find(".title-icon").html(frappe.utils.icon(icon)).toggle(true);
	}

	add_help_button(txt) {
		//
	}

	add_button(label, click, opts) {
		if (!opts) opts = {};
		// btn_class/btn_size keep their bootstrap vocabulary ("btn-primary",
		// "btn-xs") and are mapped onto the es contract; a class we don't
		// recognize passes through so custom hooks keep working
		const type = (opts.btn_class || "btn-default").replace(/^btn-/, "");
		const known = Boolean(BTN_TYPE_TO_ES[type]);
		let button = frappe.ui.button({
			label: label,
			icon: opts.icon,
			...es_opts_for_btn_type(type),
			size: opts.btn_size === "btn-xs" ? "xs" : undefined,
			css_class: ["ellipsis", !known && opts.btn_class].filter(Boolean).join(" "),
			attrs: { "data-label": encodeURIComponent(label) },
		});
		// Add actions as menu item in Mobile View (similar to "add_custom_button" in forms.js)
		let menu_item = this.add_menu_item(label, click, false);
		menu_item.parent().addClass("hidden-xl");

		button.appendTo(this.custom_actions);
		button.on("click", click);
		this.custom_actions.removeClass("hide");

		return button;
	}

	add_custom_button_group(label, icon, parent) {
		// same bridge as the header menus: the UL is a hidden item store
		// (add_custom_menu_item writes li > a there and returns the link),
		// rendered as an espresso menu per open
		let custom_btn_group = $(`
			<div class="custom-btn-group">
				<ul class="dropdown-menu" role="presentation"></ul>
			</div>
		`);

		let $button = frappe.ui.button({
			label: __(label),
			icon: icon,
			icon_right: "chevrons-up-down",
			css_class: "ellipsis",
		});
		$button.find(".es-button__label").addClass("custom-btn-group-label");
		if (icon) {
			// with an icon, mobile collapses to it alone: label and chevron
			// hide below md and page.scss squares the button. Without an icon
			// there is nothing to collapse to, so the label stays.
			$button.find(".es-button__label").addClass("hidden-xs");
			$button.children("svg").last().addClass("hidden-xs");
		}
		$button.prependTo(custom_btn_group);

		if (!parent)
			parent = frappe.is_mobile() ? this.custom_mobile_actions : this.custom_actions;
		parent.removeClass("hide").append(custom_btn_group);

		const $store = custom_btn_group.find(".dropdown-menu");
		custom_btn_group.data(
			"es_dropdown",
			new frappe.ui.Dropdown({
				trigger: $button,
				options: () => this.build_dropdown_options($store),
			})
		);

		return $store;
	}

	add_dropdown_button(parent, label, click, icon) {
		frappe.ui.toolbar.add_dropdown_button(parent, label, click, icon);
	}

	// page::form
	add_label(label) {
		this.show_form();
		return $("<label class='col-md-1 page-only-label'>" + label + " </label>").appendTo(
			this.page_form
		);
	}
	add_select(label, options) {
		var field = this.add_field({ label: label, fieldtype: "Select" });
		return field.$wrapper.find("select").empty().add_options(options);
	}
	add_data(label) {
		var field = this.add_field({ label: label, fieldtype: "Data" });
		return field.$wrapper.find("input").attr("placeholder", label);
	}
	add_date(label, date) {
		var field = this.add_field({ label: label, fieldtype: "Date", default: date });
		return field.$wrapper.find("input").attr("placeholder", label);
	}
	add_check(label) {
		return $("<div class='checkbox'><label><input type='checkbox'>" + label + "</label></div>")
			.appendTo(this.page_form)
			.find("input");
	}
	add_break() {
		// add further fields in the next line
		this.page_form.append('<div class="clearfix invisible-xs"></div>');
	}
	add_field(df, parent) {
		this.show_form();

		if (!df.placeholder) {
			df.placeholder = df.label;
		}

		df.input_class = "input-xs";

		var f = frappe.ui.form.make_control({
			df: df,
			parent: parent || this.page_form,
			only_input: df.fieldtype == "Check" ? false : true,
		});
		f.refresh();
		$(f.wrapper)
			.addClass("col-md-2")
			.attr("title", __(df.label, null, df.parent))
			.tooltip({
				delay: { show: 600, hide: 100 },
				trigger: "hover",
			});
		if (parent == this.filters) {
			this.restyle_field(f);
		}

		// html fields in toolbar are only for display
		if (df.fieldtype == "HTML") {
			return;
		}

		// hidden fields dont have $input
		if (!f.$input) f.make_input();

		f.$input.attr("placeholder", __(df.label, null, df.parent));

		if (df.fieldtype === "Check") {
			$(f.wrapper).find(":first-child").removeClass("col-md-offset-4 col-md-8");
		}

		if (df.fieldtype == "Button") {
			$(f.wrapper).find(".page-control-label").html("&nbsp;");
			f.$input.addClass("btn-xs").css({ width: "100%", "margin-top": "-1px" });
		}

		if (df["default"]) f.set_input(df["default"]);
		this.fields_dict[df.fieldname || df.label] = f;
		return f;
	}
	restyle_field(f) {
		$(f.wrapper).removeClass("col-md-2").css("margin", "0px");

		$(f.wrapper).find("select").css("width", "140px");
		$(f.wrapper).find(".select-icon").css("top", "2px");
	}
	clear_fields() {
		this.page_form.empty();
	}
	show_form() {
		this.page_form.removeClass("hide");
	}
	hide_form() {
		this.page_form.addClass("hide");
	}
	get_form_values() {
		var values = {};
		for (let fieldname in this.fields_dict) {
			let field = this.fields_dict[fieldname];
			values[fieldname] = field.get_value();
		}
		return values;
	}
	add_view(name, html) {
		let element = html;
		if (typeof html === "string") {
			element = $(html);
		}
		this.views[name] = element.appendTo($(this.wrapper).find(".page-content"));
		if (!this.current_view) {
			this.current_view = this.views[name];
		} else {
			this.views[name].toggle(false);
		}
		return this.views[name];
	}
	set_view(name) {
		if (this.current_view_name === name) return;
		this.current_view && this.current_view.toggle(false);
		this.current_view = this.views[name];

		this.previous_view_name = this.current_view_name;
		this.current_view_name = name;

		this.views[name].toggle(true);

		this.wrapper.trigger("view-change");
	}
};
