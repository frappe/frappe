frappe.provide("frappe.ui");

/**
 * @typedef {Object} PanelHeaderOpts
 * @property {string} title Heading text.
 * @property {boolean} [closable=true] Draw a close affordance in the actions row.
 * @property {function} [on_close] Called when that close affordance is clicked.
 */

/**
 * The heading a panel puts above its body: a title row with an actions slot on
 * the right, and a second row underneath for whatever the panel wants to hang
 * there (tabs, filters).
 *
 * It is separate from frappe.ui.SidebarPanel because the same heading has two
 * hosts. The sidebar draws its panels as full-height drawers; the desktop screen
 * draws notifications as an .es-popover instead, and that host is not a
 * SidebarPanel but still wants the same title, actions and tabs. Keeping the
 * markup here is what stops the two from drifting.
 *
 * The caller fills $items and $actions itself; this only positions them.
 *
 * @param {PanelHeaderOpts} opts
 * @returns {{$header: JQuery, $title: JQuery, $items: JQuery, $actions: JQuery}}
 */
frappe.ui.panel_header = function ({ title, closable = true, on_close } = {}) {
	// The close button is a sibling of the actions slot rather than inside it, so that
	// actions the caller adds land before it and close stays the rightmost thing in the
	// heading however many of them there are.
	const $header = $(`
		<div class="panel-header">
			<div class="panel-header-top">
				<div class="panel-title"></div>
				<div class="panel-header-actions">
					<div class="panel-actions"></div>
				</div>
			</div>
			<div class="panel-items"></div>
		</div>
	`);

	const $title = $header.find(".panel-title").text(title || "");
	const $actions = $header.find(".panel-actions");
	const $items = $header.find(".panel-items");

	if (closable) {
		$(`<span class="panel-close" role="button" tabindex="0" aria-label="${__("Close")}">
				${frappe.utils.icon("x", "sm")}
			</span>`)
			.on("click", () => on_close?.())
			.on("keydown", (e) => {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					on_close?.();
				}
			})
			.appendTo($header.find(".panel-header-actions"));
	}

	return { $header, $title, $items, $actions };
};
