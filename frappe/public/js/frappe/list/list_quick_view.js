// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views");

/**
 * Opens a document's real form in a resizable side panel next to the list, without
 * navigating away -- the same split-layout mechanism the attachment previewer already
 * uses on the form sidebar (a sibling panel next to .layout-main-section-wrapper,
 * driven by a --*-width custom property and a drag handle), not an overlay.
 */
// Below this, there just isn't a sensible width left over for the list once the
// panel takes its minimum share -- phones and small tablets get the plain
// navigate-to-form behavior instead, same as before this existed.
const MIN_SCREEN_WIDTH_FOR_QUICK_VIEW = 1024;

frappe.views.ListQuickView = class ListQuickView {
	constructor(list_view) {
		this.list_view = list_view;
		this.width_key = "list_view_quick_view_width";
		this.width = this.get_stored_width();

		// the container hides the outgoing page (and fires "hide" on it) when routing
		// away; that already hides this panel along with it (it's nested inside the
		// page), but reset cur_frm/keyboard state the same way an explicit close does.
		$(this.list_view.page.wrapper).on("hide", () => this.hide());
	}

	get is_available() {
		return window.innerWidth >= MIN_SCREEN_WIDTH_FOR_QUICK_VIEW;
	}

	show(docname) {
		if (!docname || !this.is_available) return;

		this.setup_panel();
		this.current_docname = docname;
		this.set_width(this.width);
		this.$panel.removeClass("hidden");
		this.render_header(docname);
		this.refresh_list_layout();
		this.load_and_render(docname);
		this.bind_escape();
	}

	hide() {
		if (!this.$panel) return;

		this.$panel.addClass("hidden");
		this.current_docname = null;

		if (typeof cur_frm !== "undefined" && cur_frm === this.frm) {
			cur_frm = null;
		}

		$(document).off("keydown.list_quick_view");
		this.refresh_list_layout();
	}

	setup_panel() {
		if (this.$panel) return;

		this.$panel = $(`<div class="list-quick-view hidden">
				<div class="list-quick-view-resize-handle"></div>
				<div class="list-quick-view-header">
					<div class="list-quick-view-title ellipsis"></div>
					<div class="list-quick-view-actions">
						<a class="es-button list-quick-view-open-link"
							data-variant="ghost" data-icon-button="true"
							title="${__("Open in full page")}"
							aria-label="${__("Open in full page")}"
						>
							${frappe.utils.icon("arrow-up-right", "sm", "", "", "", true)}
						</a>
						${frappe.ui.button.html({
							icon: "x",
							variant: "ghost",
							title: __("Close"),
							css_class: "list-quick-view-close",
						})}
					</div>
				</div>
				<div class="list-quick-view-body"></div>
			</div>`).appendTo(this.list_view.page.main.closest(".layout-main"));

		this.$header_title = this.$panel.find(".list-quick-view-title");
		this.$body = this.$panel.find(".list-quick-view-body");

		this.$panel.find(".list-quick-view-open-link").on("click", (event) => {
			if (event.ctrlKey || event.metaKey) return; // let the browser open a new tab
			event.preventDefault();
			let docname = this.current_docname;
			this.hide();
			frappe.set_route("Form", this.list_view.doctype, docname);
		});

		this.$panel.find(".list-quick-view-close").on("click", () => this.hide());

		this.$panel.find(".list-quick-view-resize-handle").on("mousedown", (event) => {
			if (event.target !== event.currentTarget) return;
			this.start_resize(event);
		});
	}

	render_header(docname) {
		let title_field = this.list_view.meta?.title_field;
		let row = title_field && (this.list_view.data || []).find((d) => d.name === docname);
		let title = (row && row[title_field]) || docname;

		this.$header_title.text(title).attr("title", title);
		this.$panel
			.find(".list-quick-view-open-link")
			.attr("href", this.list_view.get_form_link({ name: docname }));
	}

	load_and_render(docname) {
		let doctype = this.list_view.doctype;
		let doc = frappe.get_doc(doctype, docname);
		let is_fresh =
			doc &&
			frappe.model.get_docinfo(doctype, docname) &&
			(doc.__islocal || frappe.model.is_fresh(doc));

		if (is_fresh) {
			this.render_form(docname);
			return;
		}

		frappe.model.with_doc(
			doctype,
			docname,
			(name, r) => {
				// the panel may have moved on to a different row while this was in flight
				if (this.current_docname !== docname) return;
				if (r && r["403"]) return;

				if (!(locals[doctype] && locals[doctype][name])) {
					this.render_not_found(docname);
					return;
				}

				this.render_form(name);
			},
			// any error_callback (even a no-op) makes with_doc() skip its cache and
			// recheck with the server -- list rows only carry the columns shown,
			// not the full document.
			() => {}
		);
	}

	render_form(docname) {
		if (!this.frm) {
			this.frm = new frappe.ui.form.Form(
				this.list_view.doctype,
				this.$body.get(0),
				true,
				null
			);
		}

		this.with_route_state_preserved(() => this.frm.refresh(docname));
	}

	render_not_found(docname) {
		this.$body.html(`<div class="list-quick-view-unavailable">
			<div class="text-muted">${__("{0} {1} not found", [
				__(this.list_view.doctype),
				frappe.utils.escape_html(docname),
			])}</div>
		</div>`);
	}

	/**
	 * The list decides once at render time -- based on the width available then --
	 * whether each row needs horizontal scrolling and hides the row divider when it
	 * doesn't (see update_listview_classes()). Opening or resizing this panel changes
	 * that available width after the fact, so ask the list to re-derive those classes
	 * against the new width, the same way it already does on window resize.
	 */
	refresh_list_layout() {
		if (!this.list_view.update_listview_classes) return;
		let { has_assignto, assign_to_count } = this.list_view.get_assignment_stats();
		this.list_view.update_listview_classes(has_assignto, assign_to_count);
	}

	/**
	 * frm.refresh() assumes it owns the current route and mutates several route-keyed
	 * globals to match it: the page registered for this route, the browser tab title,
	 * and the breadcrumb trail. The quick view keeps the list on screen and the route
	 * unchanged, so those mutations are wrong for as long as they last -- undo them
	 * right after the call.
	 */
	with_route_state_preserved(fn) {
		let route_str = frappe.get_route_str();
		let sub_path = frappe.router.get_sub_path();
		let existing_page = frappe.ui.pages[route_str];
		let existing_title = document.title;
		let existing_original_title = frappe._original_title;
		let existing_route_title = frappe.route_titles[sub_path];
		let crumb = frappe.breadcrumbs.all[route_str];
		let existing_layout_name = crumb?.layout_name;

		fn();

		frappe.ui.pages[route_str] = existing_page;
		document.title = existing_title;
		frappe._original_title = existing_original_title;
		frappe.route_titles[sub_path] = existing_route_title;
		if (crumb) {
			crumb.layout_name = existing_layout_name;
			frappe.breadcrumbs.update();
		}
	}

	bind_escape() {
		$(document)
			.off("keydown.list_quick_view")
			.on("keydown.list_quick_view", (event) => {
				if (event.key !== "Escape") return;
				if (!this.$panel || !document.body.contains(this.$panel[0])) {
					$(document).off("keydown.list_quick_view");
					return;
				}
				this.hide();
			});
	}

	start_resize(event) {
		event.preventDefault();
		this.is_resizing = true;
		this.list_view.page.wrapper.addClass("list-quick-view-resizing");

		$(document)
			.on("mousemove.list_quick_view_resize", (event) => this.resize(event))
			.on("mouseup.list_quick_view_resize", () => this.stop_resize());
	}

	resize(event) {
		if (!this.is_resizing) return;

		let layout = this.list_view.page.wrapper.find(".layout-main").get(0);
		if (!layout) return;

		let layout_rect = layout.getBoundingClientRect();
		let width = ((layout_rect.right - event.clientX) / layout_rect.width) * 100;
		this.set_width(width);
	}

	stop_resize() {
		if (!this.is_resizing) return;

		this.is_resizing = false;
		this.list_view.page.wrapper.removeClass("list-quick-view-resizing");
		$(document).off(".list_quick_view_resize");
		this.save_width();
		this.refresh_list_layout();
	}

	set_width(width) {
		this.width = this.clamp_width(width);
		this.list_view.page.wrapper
			.get(0)
			?.style.setProperty("--list-quick-view-width", `${this.width}%`);
	}

	clamp_width(width) {
		let min_width = 25;
		let max_width = 60;
		return Math.min(Math.max(width, min_width), max_width);
	}

	get_stored_width() {
		try {
			let stored = Number(localStorage.getItem(this.width_key));
			return this.clamp_width(stored || 40);
		} catch {
			return 40;
		}
	}

	save_width() {
		try {
			localStorage.setItem(this.width_key, this.width);
		} catch {
			// localStorage can be unavailable in restricted browser contexts.
		}
	}
};
