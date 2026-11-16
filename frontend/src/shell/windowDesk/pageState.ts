// What `window.desk.state` answers: the page a person sees, as JSON an agent reads before it acts.
import { acts, type ActDialog } from "@/acts/dispatcher";
import { readDialogs } from "../dialogs/readableDialogs";

export interface StateOptions {
	/** Adds the form's visible fields on a record page, capped at about 6000 characters. */
	fields?: boolean;
}

export type PageKind = "home" | "list" | "record" | "new" | "editor" | "page" | "not_found";

export interface DeskState {
	route: string;
	page: PageKind;
	doctype?: string;
	name?: string;
	docstatus?: number;
	unsaved?: boolean;
	errors?: Record<string, string>;
	filters?: unknown[];
	sort?: unknown[];
	selected?: string[];
	fields?: Record<string, unknown>[];
	truncated?: true;
	/** A record route whose page has not registered yet: read again. */
	loading?: true;
	dialogs: ActDialog[];
}

const FIELD_CHARS = 6000;

const KINDS: Record<string, PageKind> = {
	home: "home",
	list: "list",
	"standard-list": "list",
	"saved-view": "list",
	record: "record",
	"standard-record": "record",
	"new-record": "new",
	"doctype-editor": "editor",
	"not-found": "not_found",
};

export async function readState({ fields = false }: StateOptions = {}): Promise<DeskState> {
	const page = kindOf(routeName());
	const facts = page === "list" ? listFacts() : page === "record" || page === "new" ? (await acts.factsOf("record", fields)) ?? { loading: true } : {};
	return capFields({ route: `${location.pathname}${location.search}${location.hash}`, page, ...facts, dialogs: readDialogs() });
}

function routeName(): string {
	const shell = acts.contextOf("shell") as { router?: { currentRoute: { value: { name?: unknown } } } } | undefined;
	return String(shell?.router?.currentRoute.value.name ?? "");
}

function kindOf(name: string): PageKind {
	return KINDS[name] ?? "page";
}

function listFacts() {
	const list = acts.contextOf("list") as { doctype: string; filters: unknown[]; sort: unknown[]; selection: string[] } | undefined;
	if (!list) return {};
	return { doctype: list.doctype, filters: [...list.filters], sort: [...list.sort], selected: [...list.selection] };
}

/** Drops the fields that do not fit the cap, last first. */
function capFields(state: DeskState): DeskState {
	const { fields } = state;
	if (!fields) return state;
	let kept = fields.length;
	while (kept > 0 && JSON.stringify(fields.slice(0, kept)).length > FIELD_CHARS) kept -= 1;
	return kept === fields.length ? state : { ...state, fields: fields.slice(0, kept), truncated: true };
}
