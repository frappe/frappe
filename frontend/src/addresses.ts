// The address table: every doctype on the bench and its URL spelling. Full-bench and the
// same for every user, so it is fetched and cached by `metadata_version`, not booted.

export type AddressPayload = {
	/** `{doctype: [slug, moduleSlug]}` */
	doctypes: Record<string, [string, string]>;
	/** `{moduleSlug: moduleName}`, display data. */
	modules: Record<string, string>;
};

export class Addresses {
	private readonly payload: AddressPayload;
	private readonly bySlug: Record<string, string>;

	constructor(payload: AddressPayload) {
		this.payload = payload;
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
	const res = await fetch(
		`/api/method/frappe.shell.doctypes.get_addresses?v=${encodeURIComponent(
			version
		)}`,
		{ headers: { Accept: "application/json" } }
	);
	if (!res.ok) throw new Error(`Address table failed with ${res.status}`);
	return new Addresses((await res.json()).message);
}
