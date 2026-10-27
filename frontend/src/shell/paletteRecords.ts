// The palette's Records group, matched on the server as the reader types, and its pinned
// "Find in <doctype>" row, which opens the current doctype's list filtered by the text.
import { shallowRef } from "vue";
import { runMethod } from "@framework/ui/api";
import { getFilterableFields, serializeFilters } from "@framework/ui/Filter";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { __ } from "@/i18n";
import { routeFor, urlFor } from "@/router/routeFor";
import type { PaletteRow } from "./palette";
import type { PaletteContext, PaletteGroup } from "./paletteGroups";
import { openPlace } from "./palettePlaces";

interface FoundRecord {
	doctype: string;
	name: string;
	label: string;
}

const SHORTEST_QUERY = 2;
const QUIET_MS = 200;
const PAGE_ROUTES = new Set(["list", "standard-list", "saved-view", "record", "standard-record"]);

/** The server's records for the query typed last, or where the question stands. */
class RecordSearch {
	readonly found = shallowRef<FoundRecord[] | "searching" | "failed">([]);
	private timer: ReturnType<typeof setTimeout> | undefined;
	private asking: AbortController | undefined;

	/** Asks once the typing has paused, and drops the question asked before. */
	follow(query: string, doctype: string | null) {
		clearTimeout(this.timer);
		this.asking?.abort();
		const text = query.trim();
		if (text.length < SHORTEST_QUERY) {
			this.found.value = [];
			return;
		}
		this.found.value = "searching";
		this.timer = setTimeout(() => this.ask(text, doctype), QUIET_MS);
	}

	private async ask(txt: string, doctype: string | null) {
		const asking = (this.asking = new AbortController());
		try {
			const { data } = await runMethod<FoundRecord[]>(
				"frappe.desk.palette.search_records",
				doctype ? { txt, doctype } : { txt },
				{ http: "GET", signal: asking.signal }
			);
			if (!asking.signal.aborted) this.found.value = data;
		} catch {
			if (!asking.signal.aborted) this.found.value = "failed";
		}
	}
}

const recordSearch = new RecordSearch();

export const records: PaletteGroup = {
	get label() {
		return __("Records");
	},
	follow: (query, context) => recordSearch.follow(query, pageDoctype(context)),
	rows: (_query, context) => {
		const found = recordSearch.found.value;
		if (found === "searching") return [searchingRow()];
		if (found === "failed") return [failedRow()];
		return found.map((record) => recordRow(record, context));
	},
};

/** "Find “<text>” in <doctype>", on a list or record page once something is typed, unless narrowed. */
export function findRow(query: string, context: PaletteContext): PaletteRow[] {
	const text = query.trim();
	const doctype = pageDoctype(context);
	if (!text || !doctype || context.narrowed()) return [];
	return [
		{
			id: "find",
			label: __("Find “{0}” in {1}", [text, __(doctype)]),
			icon: "lucide-search",
			run: () => context.router.push(findRoute(doctype, text)),
		},
	];
}

function searchingRow(): PaletteRow {
	return { id: "records:searching", label: __("Searching…"), pending: true, run: () => {} };
}

function failedRow(): PaletteRow {
	return {
		id: "records:failed",
		label: __("Could not search records"),
		icon: "lucide-circle-alert",
		disabled: true,
		run: () => {},
	};
}

function recordRow(record: FoundRecord, context: PaletteContext): PaletteRow {
	const href = urlFor(record.doctype, String(record.name));
	return {
		id: `record:${record.doctype}/${record.name}`,
		label: String(record.label),
		description: __(record.doctype),
		icon: "lucide-file-text",
		href,
		run: () => openPlace(href, context),
	};
}

/** The doctype of the list or record on screen; a Single has no list to find in. */
function pageDoctype({ router, addresses }: PaletteContext): string | null {
	const route = router.currentRoute.value;
	if (!PAGE_ROUTES.has(String(route.name))) return null;
	const doctype = addresses.doctypeOf(String(route.params.doctype ?? ""));
	return doctype && !addresses.isSingle(doctype) ? doctype : null;
}

function findRoute(doctype: string, text: string) {
	const [[fieldname, operator, value]] = serializeFilters([
		{ fieldname: findField(doctype), operator: "like", value: text },
	]);
	return routeFor(doctype, null, { query: { [fieldname]: JSON.stringify([operator, value]) } });
}

/** As desk v1 did: the title field when the list can filter on it, else the name. */
function findField(doctype: string): string {
	const meta = useDoctypeMeta(doctype).meta.value;
	const title = meta?.title_field;
	const filterable = getFilterableFields(meta?.fields ?? [], doctype);
	return title && filterable.some((field) => field.fieldname === title) ? title : "name";
}
