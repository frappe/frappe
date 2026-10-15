import "../connections_dialog";

const SHOWN_IN_SIDEBAR = 4;

// doctype icons can be lucide names, legacy "fa fa-*" classes or empty
frappe.ui.form.connection_icon_name = (icon) =>
	icon && !/\s/.test(icon) && document.getElementById(`icon-${icon}`) ? icon : "file";

frappe.ui.form.connection_icon = (icon) =>
	frappe.utils.icon(frappe.ui.form.connection_icon_name(icon), "sm");

// the server stops counting at 100, so 100 means "100 or more"
frappe.ui.form.connection_count = (count) => (cint(count) > 99 ? "99+" : count);

frappe.ui.form.SidebarConnections = class SidebarConnections {
	constructor({ frm, wrapper }) {
		this.frm = frm;
		this.wrapper = $(wrapper);
		this.wrapper.on("click", ".form-connections-item, .form-connections-all", (e) => {
			this.open_dialog(e.currentTarget.dataset.doctype);
		});
	}

	refresh() {
		const dashboard = this.frm.dashboard;
		this.wrapper.addClass("hidden").empty();
		if (!dashboard?.has_connections()) return;

		const request = (this.request = {});
		// counts cost a query per linked type: fetch them once the section is on screen
		this.when_in_view(() => {
			if (request !== this.request) return;
			dashboard.load_counts().then(() => {
				if (request === this.request) this.render(dashboard.get_connections());
			});
		});
	}

	when_in_view(callback) {
		this.observer?.disconnect();
		// the section is hidden until rendered
		if (!this.marker)
			this.marker = $('<div class="form-connections-marker">').insertBefore(this.wrapper);
		this.observer = new IntersectionObserver((entries) => {
			if (entries.some((entry) => entry.isIntersecting)) {
				this.observer.disconnect();
				callback();
			}
		});
		this.observer.observe(this.marker[0]);
	}

	render(connections) {
		const linked = connections
			.filter((c) => c.count)
			.sort((a, b) => (cint(b.count) || Infinity) - (cint(a.count) || Infinity));
		const shown = [...linked, ...connections.filter((c) => !c.count)].slice(
			0,
			SHOWN_IN_SIDEBAR
		);

		const escape = frappe.utils.escape_html;
		const row = (doctype, icon, label, count = "") => `<button type="button"
			class="form-connections-item" ${doctype ? `data-doctype="${escape(doctype)}"` : ""}>
			<span class="form-sidebar-label">
				${icon}
				<span class="ellipsis">${escape(label)}</span>
			</span>
			<span class="form-connections-count">${count}</span>
		</button>`;
		const rows = shown.map((c) =>
			row(
				c.doctype,
				frappe.ui.form.connection_icon(c.icon),
				__(c.doctype),
				c.count ? frappe.ui.form.connection_count(c.count) : ""
			)
		);
		const hidden = connections.length - shown.length;
		if (hidden > 0) {
			rows.push(
				row(
					"",
					frappe.utils.icon("ellipsis", "sm"),
					hidden === 1 ? __("1 more type") : __("{0} more types", [hidden])
				)
			);
		}

		this.wrapper
			.html(
				`<span class="form-sidebar-items">
					<span class="form-sidebar-label">
						<span class="ellipsis">${__("Connections")}</span>
					</span>
					${frappe.ui.button.html({
						label: __("View all"),
						variant: "ghost",
						css_class: "form-connections-all",
					})}
				</span>
				${rows.length ? `<div class="form-connections-list">${rows.join("")}</div>` : ""}`
			)
			.removeClass("hidden");
	}

	open_dialog(doctype) {
		new frappe.ui.form.ConnectionsDialog({ frm: this.frm, doctype });
	}
};
