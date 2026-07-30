frappe.provide("frappe.ui");
frappe.ui.SidePanel = class SidePanel {
	constructor({ parent, width_storage_key = "side_panel_width" } = {}) {
		this.parent = parent;
		this.width_storage_key = width_storage_key;
		this.min_width = 360;
		this.is_open = false;
		this.make();
	}

	make() {
		this.$resize_handle = $(`
			<div class="side-panel-resize-handle hidden">
				<div class="side-panel-resize-grip"></div>
			</div>
		`).appendTo(this.parent);

		this.$panel = $(`
			<div class="side-panel-preview hidden">
				<div class="side-panel-header">
					<div class="side-panel-title">
						<span class="side-panel-doctype ellipsis"></span>
						<span class="side-panel-title-sep">/</span>
						<span class="side-panel-docname ellipsis"></span>
						<span class="side-panel-indicator"></span>
					</div>
					<div class="side-panel-actions">
						${frappe.ui.button.html({
							icon: "arrow-up-right",
							variant: "ghost",
							size: "sm",
							title: __("Open full page"),
							css_class: "side-panel-open-full",
						})}
						${frappe.ui.button.html({
							icon: "x",
							variant: "ghost",
							size: "sm",
							title: __("Close"),
							css_class: "side-panel-close",
						})}
					</div>
				</div>
				<div class="side-panel-body"></div>
			</div>
		`).appendTo(this.parent);

		this.$doctype = this.$panel.find(".side-panel-doctype");
		this.$title = this.$panel.find(".side-panel-docname");
		this.$indicator = this.$panel.find(".side-panel-indicator");
		this.$body = this.$panel.find(".side-panel-body");
		this.$open_full_btn = this.$panel.find(".side-panel-open-full");

		this.$panel.find(".side-panel-close").on("click", () => this.close());

		this.$open_full_btn.on("click", (e) => {
			e.preventDefault();
			this.on_open_full_page && this.on_open_full_page();
		});

		this.setup_resize();
		this.apply_saved_width();
		this.watch_grid_popups();
	}

	watch_grid_popups() {
		this.teleported = new Map();

		this.grid_popup_observer = new MutationObserver((mutations) => {
			for (const { type, attributeName, target } of mutations) {
				if (type !== "attributes" || attributeName !== "class") continue;
				if (!(target instanceof HTMLElement) || !target.classList.contains("grid-row"))
					continue;

				if (target.classList.contains("grid-row-open")) {
					this.teleport_popup(target);
				} else {
					this.restore_popup(target);
				}
			}
		});
		this.grid_popup_observer.observe(this.$body.get(0), {
			attributes: true,
			attributeFilter: ["class"],
			subtree: true,
		});
	}

	teleport_popup(grid_row_el) {
		if (this.teleported.has(grid_row_el)) return;
		const popup = grid_row_el.querySelector(":scope > .form-in-grid");
		if (!popup) return;
		const portal = document.createElement("div");
		portal.className = "grid-row-open side-panel-popup-portal";
		document.body.appendChild(portal);
		this.teleported.set(grid_row_el, { popup, portal, next_sibling: popup.nextSibling });
		portal.appendChild(popup);
	}

	restore_popup(grid_row_el) {
		const entry = this.teleported.get(grid_row_el);
		if (!entry) return;
		this.teleported.delete(grid_row_el);
		if (entry.next_sibling) {
			grid_row_el.insertBefore(entry.popup, entry.next_sibling);
		} else {
			grid_row_el.appendChild(entry.popup);
		}
		entry.portal.remove();
	}

	set_width(width) {
		this.$panel.css("width", width + "px");
		this.$resize_handle.css("right", width - 4 + "px");
	}

	setup_resize() {
		const handle_el = this.$resize_handle.get(0);
		let start_x = 0;
		let start_width = 0;

		const on_move = (e) => {
			// dragging left widens the panel (it is anchored to the right edge)
			let width = start_width + (start_x - e.clientX);
			width = Math.max(this.min_width, Math.min(width, window.innerWidth * 0.9));
			this.set_width(width);
		};

		const on_up = (e) => {
			handle_el.releasePointerCapture(e.pointerId);
			handle_el.removeEventListener("pointermove", on_move);
			handle_el.removeEventListener("pointerup", on_up);
			handle_el.removeEventListener("pointercancel", on_up);
			this.$panel.removeClass("side-panel-resizing");
			this.$resize_handle.removeClass("side-panel-resizing");
			this.save_width(this.$panel.width());
		};

		handle_el.addEventListener("pointerdown", (e) => {
			e.preventDefault();
			start_x = e.clientX;
			start_width = this.$panel.width();
			this.$panel.addClass("side-panel-resizing");
			this.$resize_handle.addClass("side-panel-resizing");
			handle_el.setPointerCapture(e.pointerId);
			handle_el.addEventListener("pointermove", on_move);
			handle_el.addEventListener("pointerup", on_up);
			handle_el.addEventListener("pointercancel", on_up);
		});
	}

	apply_saved_width() {
		const saved = parseInt(localStorage.getItem(this.width_storage_key));
		if (saved && !isNaN(saved)) {
			const width = Math.max(this.min_width, Math.min(saved, window.innerWidth * 0.9));
			this.set_width(width);
		}
	}

	save_width(width) {
		localStorage.setItem(this.width_storage_key, Math.round(width));
	}

	restore_all_teleported_popups() {
		for (const grid_row_el of Array.from(this.teleported.keys())) {
			this.restore_popup(grid_row_el);
		}
	}

	open({ title, doctype, render, on_open_full_page }) {
		this.restore_all_teleported_popups();

		this.$doctype.text(doctype || "").attr("title", doctype || "");
		this.$title.text(title || "").attr("title", title || "");
		this.$indicator.empty();

		this.on_open_full_page = on_open_full_page || null;
		this.$open_full_btn.toggle(Boolean(on_open_full_page));

		this.is_open = true;
		this.$panel.removeClass("hidden");
		this.$resize_handle.removeClass("hidden");
		this.bind_escape();

		this.open_id = (this.open_id || 0) + 1;
		const my_open_id = this.open_id;
		const previous = this.rendered;
		const is_current = () => this.is_open && this.open_id === my_open_id;
		const set_header = ({ title, indicator } = {}) => {
			if (!is_current()) return;
			if (title) this.$title.text(title).attr("title", title);
			this.$indicator.empty();
			if (indicator) {
				const [label, color] = indicator;
				this.$indicator.append(frappe.ui.badge.html({ label, theme: color, size: "sm" }));
			}
		};
		const result = render && render(this.$body.get(0), { set_header, previous, is_current });
		Promise.resolve(result).then((value) => {
			if (is_current()) this.rendered = value;
		});
	}

	close() {
		if (!this.is_open) return;
		this.is_open = false;
		this.$panel.addClass("hidden");
		this.$resize_handle.addClass("hidden");
		if (this.rendered && typeof this.rendered.side_panel_on_close === "function") {
			this.rendered.side_panel_on_close();
		}
		this.rendered = null;
		this.restore_all_teleported_popups();
		this.$body.empty();
		this.on_open_full_page = null;
		this.unbind_escape();
	}

	bind_escape() {
		if (this.escape_handler) return; // open() no longer implies a fresh bind each time
		this.escape_handler = (e) => {
			if (e.key !== "Escape") return;
			// keyboard.js closes an open row-edit popup on this same keypress; defer to it.
			if (this.$panel.find(".grid-row-open").length) return;
			this.close();
		};
		$(document).on("keydown", this.escape_handler);
	}

	unbind_escape() {
		if (this.escape_handler) {
			$(document).off("keydown", this.escape_handler);
			this.escape_handler = null;
		}
	}
};
