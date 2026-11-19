// The permissions table's columns by DocType kind, and why a rule cannot take a right.
import { __ } from "@/i18n";
import type { PermissionRow, Right } from "./settingsModel";
import type { DoctypeKind } from "./settingsRows";

export const RIGHT_LABELS: Record<Right, string> = {
	select: "Select",
	read: "Read",
	write: "Write",
	create: "Create",
	delete: "Delete",
	submit: "Submit",
	cancel: "Cancel",
	amend: "Amend",
	print: "Print",
	email: "Email",
	report: "Report",
	import: "Import",
	export: "Export",
	share: "Share",
};

export const RIGHT_HELP: Partial<Record<Right, string>> = {
	select: "Pick it in a Link field, without opening it.",
	report: "Open the report view.",
	export: "Download records as a spreadsheet.",
	import: "Bring records in from a spreadsheet.",
	print: "Print and make PDFs.",
	email: "Send a record by email.",
	share: "Share a record with another person.",
};

/** The rights a level above 0 cannot have: it only reads and writes its fields. */
const NOT_ABOVE_LEVEL_0: Right[] = ["create", "submit", "cancel", "amend"];

/** The rights with their own column; Read and Write on a Single. */
export function columns(kind: DoctypeKind): Right[] {
	if (kind === "single") return ["read", "write"];
	const base: Right[] = ["read", "write", "create", "delete"];
	return kind === "submittable" ? [...base, "submit", "cancel", "amend"] : base;
}

/** The rest, under "More". A Single has no report, import or export. */
export function moreRights(kind: DoctypeKind): Right[] {
	const all: Right[] = ["select", "report", "export", "import", "print", "email", "share"];
	return kind === "single" ? all.filter((right) => !["report", "import", "export"].includes(right)) : all;
}

/** Why the rule cannot take the right; "" when it can. */
export function rightRefusal(row: PermissionRow, right: Right, allowImport: boolean): string {
	if (row[right]) return "";
	if (row.permlevel > 0 && NOT_ABOVE_LEVEL_0.includes(right)) {
		return __("A rule above level 0 only reads and writes its fields.");
	}
	if (right === "import" && !allowImport) return __("Turn on Allow import in List and search first.");
	return "";
}
