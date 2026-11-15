// The widget client contract: what a Widget Type's renderer imports.
//
//     import { useWidget } from "@framework/ui/widget";
//     const { widget, config, data, size } = useWidget();
//
// The workspace frame fetches a widget's data and hands it over; a renderer only draws. A type an
// app ships is its own island, and its entry is `export const mount = defineWidget(Component)`.

import { inject, provide } from "vue";
import { mountVueIsland } from "../island/index.js";

export const widgetKey = Symbol("widget");

/** The widget the frame is drawing: refs, plus `setFilters` and `refresh`. */
export function useWidget() {
	const widget = inject(widgetKey, null);
	if (!widget) throw new Error("useWidget() is called outside a widget");
	return widget;
}

export function provideWidget(widget) {
	provide(widgetKey, widget);
}

/** An island entry for a widget renderer. The frame passes the widget as the `widget` prop. */
export function defineWidget(component) {
	return (el, context) =>
		mountVueIsland(el, {
			...context,
			component,
			configure: (app) => app.provide(widgetKey, context.props.widget),
		});
}

/** The desk route a link to a DocType, Report, Page or Dashboard opens. */
export function routeFor(link) {
	return window.frappe.utils.generate_route({
		name: link.link_to,
		type: link.type,
		is_query_report: link.is_query_report,
		doctype: link.ref_doctype,
		doc_view: link.doc_view,
		kanban_board: link.kanban_board,
		report_ref_doctype: link.report_ref_doctype,
	});
}

/** Opens a link the way desk does: a URL in a new tab, `New` as a quick entry, else its route. */
export function openWidget(link, event) {
	const frappe = window.frappe;
	if (link.type === "URL") return window.open(link.url, "_blank");
	if (link.type === "DocType" && link.doc_view === "New") {
		// no redirect after the record is made
		return frappe.ui.form.make_quick_entry(link.link_to, () => {});
	}
	if (link.type === "DocType" && link.filters?.length)
		frappe.route_options = routeOptions(link.filters);
	if (event?.ctrlKey || event?.metaKey) frappe.open_in_new_tab = true;
	frappe.set_route(routeFor(link));
}

// `[field, op, value]` rows as the list view takes them; a child table's row stays out
function routeOptions(filters) {
	const rows = filters.filter((row) => row.length === 3);
	return Object.fromEntries(rows.map(([field, op, value]) => [field, [op, value]]));
}
