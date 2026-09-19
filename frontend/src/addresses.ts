// The address table: every doctype on the bench and its URL spelling. Full-bench and the
// same for every user, so it is fetched and cached by `metadata_version`, not booted.

import { runMethod } from "@framework/ui/api";

export type AddressPayload = {
	/** `{doctype: [slug, moduleSlug]}` */
	doctypes: Record<string, [string, string]>;
	/** `{moduleSlug: moduleName}`, display data. */
	modules: Record<string, string>;
	/** The doctypes with no list: their address opens the document itself. */
	singles?: string[];
};

export class Addresses {
	private readonly payload: AddressPayload;
	private readonly bySlug: Record<string, string>;
	private readonly singles: Set<string>;

	constructor(payload: AddressPayload) {
		this.payload = payload;
		this.singles = new Set(payload.singles ?? []);
		this.bySlug = {};
		for (const [doctype, [slug]] of Object.entries(payload.doctypes)) {
			this.bySlug[slug] = doctype;
		}
	}

	/** The real doctype behind a URL segment, or null. */
	doctypeOf(slug: string): string | null {
		// `Object.hasOwn`, not a bare read: `/apps/crm/constructor` would otherwise pass the
		// guard and hand the page a function.
		return Object.hasOwn(this.bySlug, slug) ? this.bySlug[slug] : null;
	}

	/** `[slug, moduleSlug]` for a doctype, or null if the site has never heard of it. */
	addressOf(doctype: string): [string, string] | null {
		return Object.hasOwn(this.payload.doctypes, doctype)
			? this.payload.doctypes[doctype]
			: null;
	}

	/** A single has no list; `routeFor` sends it to the document itself. */
	isSingle(doctype: string): boolean {
		return this.singles.has(doctype);
	}

	/** The slug a doctype name resolves to, case-insensitively. */
	slugOfName(segment: string): string | null {
		const match = Object.entries(this.payload.doctypes).find(
			([doctype]) => doctype.toLowerCase() === segment.toLowerCase()
		);
		return match?.[1][0] ?? null;
	}

	/**
	 * The slug a module name is spelled with, or null. The scrub is never re-implemented here.
	 */
	slugOfModule(name: string): string | null {
		const match = Object.entries(this.payload.modules).find(
			([, moduleName]) => moduleName === name
		);
		return match?.[0] ?? null;
	}

	moduleName(slug: string): string | null {
		return Object.hasOwn(this.payload.modules, slug)
			? this.payload.modules[slug]
			: null;
	}

	hasModule(slug: string): boolean {
		return Object.hasOwn(this.payload.modules, slug);
	}
}

export async function fetchAddresses(version: string): Promise<Addresses> {
	// Cached server-side for a year; `v=` is the only invalidator.
	const response = await runMethod<AddressPayload>(
		"frappe.shell.doctypes.get_addresses",
		{ v: version },
		{ http: "GET" }
	);
	return new Addresses(response.data);
}
