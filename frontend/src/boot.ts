// The shell's boot payload: small, per prefix, separate from desk v1's `frappe.sessions.get()`.

/**
 * One resolved navigation item; the rail and a sidebar share this shape. A blank field
 * is omitted, never sent as `null`.
 */
export type NavigationItem = {
	key: string;
	item_type: string;
	parent_key?: string;
	link_doctype?: string;
	link_to?: string;
	/**
	 * An absolute href off this prefix (a `Link` item, or a contributed item that switches
	 * app). Following it is a full document load, so the row is an `<a>`, not a `RouterLink`.
	 */
	url?: string;
	payload?: Record<string, unknown>;
	label?: string;
	icon?: string;
	collapsible?: 1;
	keep_closed?: 1;
};

export type Navigation = {
	rail: NavigationItem[];
	/**
	 * Keyed by scrubbed address, the string a `Sidebar` rail item holds in `link_to`, never
	 * by record name. An address that resolved to nothing is absent, not empty.
	 */
	sidebars: Record<string, NavigationItem[]>;
};

export type Boot = {
	// --- framework core ---
	frappe_version: string;
	site_name: string;
	socketio_port: number;
	read_only_mode: boolean;
	csrf_token: string;
	setup_complete: boolean;
	sysdefaults: Record<string, unknown>;
	timezone: string;
	user: { name: string; full_name: string; user_image?: string };
	lang: string;
	translations_version: string;
	app_order: string[];

	// --- routing ---
	//
	// `shell_base` is the composed path (`/apps/crm`), so the literal `/apps` never appears
	// in JS. It is `/apps` itself on the index, which belongs to no app.
	shell_base: string;
	app: string | null;

	// Every active app, not just this one: a link into a foreign app needs that app's shape.
	prefixes: Record<string, { app: string; modular: boolean }>;

	// Invalidates the address table, which is fetched separately; see `addresses.ts`.
	metadata_version: string;

	// --- navigation ---
	//
	// The rail and every sidebar in this prefix, resolved and merged server-side so a rail
	// click costs no request. Absent on the index. What an app contains is `contents.ts`.
	navigation?: Navigation;

	// Present on the index only.
	apps?: {
		app: string;
		prefix: string;
		title: string;
		logo?: string;
		route: string;
	}[];

	// --- the declaring app's contribution, merged under core ---
	[appKey: string]: unknown;
};

export class BootUnauthorized extends Error {}

export async function fetchBoot(): Promise<Boot> {
	// The server needs the path to know which app's contribution to merge in.
	const res = await fetch(
		`/api/method/frappe.shell.boot.get_boot?path=${encodeURIComponent(
			location.pathname
		)}`,
		{ headers: { Accept: "application/json" } }
	);

	// 401 as well as 403: an expired session answers 401, and the user needs the way back
	// to login, not a generic failure.
	if (res.status === 401 || res.status === 403)
		throw new BootUnauthorized("Not permitted");
	if (!res.ok) throw new Error(`Boot failed with ${res.status}`);

	const boot: Boot = (await res.json()).message;
	// frappe-ui's request layer reads the token from this global; the shell has no Jinja to set it.
	window.csrf_token = boot.csrf_token;
	return boot;
}
