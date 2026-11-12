// How a column's cell keys draw one cell: the icon, badge theme or date text it picks for a value.
import type { BadgeSpec, ListCell } from "@/contributions/types";
import { currentSession } from "@framework/ui/useSession";
import { dayjs, type BadgeProps } from "frappe-ui";

export interface CellView {
	icon?: string;
	theme?: BadgeProps["theme"];
	/** A badge function's own text; absent means the field's own text. */
	label?: string;
	/** The `[fieldname, operator, value]` triples a click on the badge applies. */
	filters?: NonNullable<BadgeSpec["filters"]>;
	/** A formatted date; absent means the field's own text. */
	text?: string;
	/** The full date a formatted one stands for. */
	title?: string;
}

// `FieldCell` draws these itself, so an app's cell would show their raw value in its place.
const OWN_CELL_FIELDTYPES = new Set(["Check", "Rating", "Color", "Attach", "Attach Image", "Image"]);

/** What `cell` draws for `value` in `row`, or null when it names nothing for it and the default cell shows. */
export function resolveCell(
	cell: ListCell | undefined,
	value: unknown,
	fieldtype?: string,
	row: Record<string, any> = {}
): CellView | null {
	if (!cell || (fieldtype && OWN_CELL_FIELDTYPES.has(fieldtype))) return null;
	// A badge function reads the row, so it answers for an empty value too.
	if (typeof cell.badge === "function") {
		const badge = badgeOf(cell.badge, row);
		if (badge) return badge;
	}
	if (value == null || value === "") return null;
	const key = String(value);
	const icon = named(cell.icons, key);
	if (icon) return { icon: iconName(icon) };
	const theme = typeof cell.badge === "function" ? undefined : named(cell.badge, key);
	if (theme) return { theme: themeOf(theme) };
	const date = cell.format && fieldtype ? formatted(key, fieldtype, cell.format) : null;
	if (!cell.icon && !date) return null;
	return { icon: cell.icon && iconName(cell.icon), ...date };
}

/** Whether `cell` draws a Check column as a switch. */
export function isSwitchCell(cell: ListCell | undefined, fieldtype?: string): boolean {
	return Boolean(cell?.switch) && fieldtype === "Check";
}

// frappe-ui's Badge has no `orange`; its warm theme is `amber`.
function themeOf(theme: string): BadgeProps["theme"] {
	return (theme === "orange" ? "amber" : theme) as BadgeProps["theme"];
}

// A script's function runs in the table's render; its error leaves the default cell, not a blank table.
function badgeOf(badge: (row: Record<string, any>) => BadgeSpec | null | undefined, row: Record<string, any>): CellView | null {
	let spec: BadgeSpec | null | undefined;
	try {
		spec = badge(row);
	} catch (error) {
		console.error("A column's badge function threw:", error);
		return null;
	}
	if (!spec || typeof spec !== "object") return null;
	const view: CellView = { theme: themeOf(spec.theme ?? "gray") };
	if (spec.label != null) view.label = String(spec.label);
	if (Array.isArray(spec.filters) && spec.filters.length) view.filters = spec.filters;
	return view;
}

function named<T>(map: Record<string, T> | undefined, key: string): T | undefined {
	return map && Object.hasOwn(map, key) ? map[key] : undefined;
}

/** The sprite names its symbols without frappe-ui's `lucide-` prefix. */
function iconName(name: string): string {
	return name.replace(/^lucide-/, "");
}

function formatted(value: string, fieldtype: string, format: string): Pick<CellView, "text" | "title"> | null {
	if (fieldtype !== "Date" && fieldtype !== "Datetime") return null;
	// A Datetime is stored on the system clock, which the session carries.
	const zone = currentSession()?.timezone;
	const stamp = fieldtype === "Datetime" && zone ? dayjs.tz(value, zone) : dayjs(value);
	if (!stamp.isValid()) return null;
	return {
		text: stamp.format(format),
		title: stamp.format(fieldtype === "Datetime" ? "ddd, MMM D, YYYY | hh:mm a" : "ddd, MMM D, YYYY"),
	};
}
