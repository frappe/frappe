// The address table: every doctype on the bench, and how each one is spelled in a URL.
//
// Fetched, not booted. It used to be `boot.doctype_slugs`, scoped to one app because
// a doctype was addressable only inside its owner's prefix. The prefix is a LENS
// (#42210) -- every doctype is addressable under every prefix -- so the table went
// full-bench, broke the 40 KB boot budget on an ERPNext bench, and became
// byte-identical for every user and every prefix in the same move. That last property
// is what let it leave boot rather than be trimmed: it is now cacheable, keyed on
// `metadata_version`, exactly as translations are keyed on `translations_version`
// (#42070).
//
// It carries the module too (#42211), because a modular app's address is
// `/<module>/<doctype>/<name>` and the two halves must not be able to disagree. The
// server sends the module SLUG, so `frappe.scrub` is never re-implemented here.

export type AddressPayload = {
  /** `{doctype: [slug, moduleSlug]}` */
  doctypes: Record<string, [string, string]>;
  /** `{moduleSlug: moduleName}` -- display data, 35 entries against 553 doctypes. */
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
    // `Object.hasOwn`, not a bare read: a plain object inherits from
    // Object.prototype, so `/apps/crm/constructor` would otherwise pass the guard
    // and hand the page a function.
    return Object.hasOwn(this.bySlug, slug) ? this.bySlug[slug] : null;
  }

  /** `[slug, moduleSlug]` for a doctype, or null if the site has never heard of it. */
  addressOf(doctype: string): [string, string] | null {
    return Object.hasOwn(this.payload.doctypes, doctype)
      ? this.payload.doctypes[doctype]
      : null;
  }

  /** The slug a doctype NAME resolves to, case-insensitively -- the de-slug path. */
  slugOfName(segment: string): string | null {
    const match = Object.entries(this.payload.doctypes).find(
      ([doctype]) => doctype.toLowerCase() === segment.toLowerCase()
    );
    return match?.[1][0] ?? null;
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
  // `v=` in the query string is the ONLY thing that invalidates this: the endpoint
  // carries `@http_cache(max_age=31536000)`, a full year, private.
  const res = await fetch(
    `/api/method/frappe.shell.doctypes.get_addresses?v=${encodeURIComponent(
      version
    )}`,
    { headers: { Accept: "application/json" } }
  );
  if (!res.ok) throw new Error(`Address table failed with ${res.status}`);
  return new Addresses((await res.json()).message);
}
