// How a contributed `cells` entry draws one cell: the icon, badge theme or date text it picks for a value.
import type { ListCell, ListHandlers } from "@/contributions/types";
import { currentSession } from "@framework/ui/useSession";
import { dayjs, type BadgeProps } from "frappe-ui";

export interface CellView {
	icon?: string;
	theme?: BadgeProps["theme"];
	/** A formatted date; absent means the field's own text. */
	text?: string;
	/** The full date a formatted one stands for. */
	title?: string;
}

// `FieldCell` draws these itself, so an app's cell would show their raw value in its place.
const OWN_CELL_FIELDTYPES = new Set(["Check", "Rating", "Color", "Attach", "Attach Image", "Image"]);

/** Every contributing app's `cells` by fieldname; the first app to name a fieldname wins. */
export function contributedCells(contributed: ListHandlers[]): Record<string, ListCell> {
	const cells: Record<string, ListCell> = {};
	for (const handlers of contributed) {
		for (const [fieldname, cell] of Object.entries(handlers.cells ?? {})) cells[fieldname] ??= cell;
	}
	return cells;
}

/** What `cell` draws for `value`, or null when it names nothing for it and the default cell shows. */
export function resolveCell(cell: ListCell | undefined, value: unknown, fieldtype?: string): CellView | null {
	if (!cell || value == null || value === "" || (fieldtype && OWN_CELL_FIELDTYPES.has(fieldtype))) return null;
	const key = String(value);
	const icon = named(cell.icons, key);
	if (icon) return { icon: iconName(icon) };
	const theme = named(cell.badge, key);
	// frappe-ui's Badge has no `orange`; its warm theme is `amber`.
	if (theme) return { theme: theme === "orange" ? "amber" : theme };
	const date = cell.format && fieldtype ? formatted(key, fieldtype, cell.format) : null;
	if (!cell.icon && !date) return null;
	return { icon: cell.icon && iconName(cell.icon), ...date };
}

/** Whether `cell` draws a Check column as a switch. */
export function isSwitchCell(cell: ListCell | undefined, fieldtype?: string): boolean {
	return Boolean(cell?.switch) && fieldtype === "Check";
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
