// Small helpers shared by the frappe.ui.* component helpers.

/**
 * Warn and drop values that aren't in the allowed list.
 * Without this, a typo like variant: "prmary" would silently render with
 * the default style and be easy to miss.
 */
export function validated(value, allowed, option, component) {
	if (value == null) return null;
	if (!allowed.includes(value)) {
		console.warn(
			`frappe.ui.${component}: unknown ${option} "${value}" — expected ${allowed.join(
				" | "
			)}`
		);
		return null;
	}
	return value;
}

/**
 * True when a URL's scheme runs code (javascript:/vbscript:/data:) — even
 * when it's hidden behind characters the browser drops before it reads the
 * scheme. Per the URL spec the browser removes tab/newline/CR from anywhere
 * in the URL, and any leading C0 control or space; so "java&#9;script:" and
 * "\x01javascript:" both run as javascript:. A plain `^\s*` check misses
 * both: `\s` doesn't match the C0 controls outside tab/newline/CR, and `^`
 * doesn't see an interior tab. Normalize exactly the way the browser does,
 * THEN test. Escaping can't make these safe — the caller must refuse them.
 */
export function has_unsafe_scheme(value) {
	const bare = String(value)
		// removed anywhere in the URL by the browser
		.replace(/[\t\n\r]/g, "")
		// any leading C0 control (U+0000-U+0020) or space, before the scheme
		.replace(/^[\u0000-\u0020]+/, "");
	return /^(javascript|vbscript|data):/i.test(bare);
}

/**
 * Refuse hrefs on schemes that run code — escaping can't make those safe.
 */
export function safe_href(href, component) {
	if (!href) return null;
	if (has_unsafe_scheme(href)) {
		console.warn(`frappe.ui.${component}: refusing unsafe href "${href}"`);
		return null;
	}
	return href;
}

// same OS mapping as frappe.ui.keys.get_shortcut_label, but per key — that
// util returns one joined string ("⌘P") while the components render one
// <kbd> per key (menus, tooltips)
const MAC_KEY_SYMBOLS = { ctrl: "⌘", meta: "⌘", cmd: "⌘", alt: "⌥", shift: "⇧" };

/**
 * Raw combo ("ctrl+p") → per-key display strings in OS form (["⌘", "P"] on
 * Mac). Arrays pass through as already-formatted keys. Display only —
 * binding stays the caller's job.
 */
export function shortcut_keys(shortcut) {
	if (Array.isArray(shortcut)) return shortcut.map(String);
	const mac = frappe.utils.is_mac && frappe.utils.is_mac();
	return String(shortcut)
		.split("+")
		.map((key) => key.trim())
		.filter(Boolean)
		.map((key) => {
			if (mac && MAC_KEY_SYMBOLS[key.toLowerCase()]) {
				return MAC_KEY_SYMBOLS[key.toLowerCase()];
			}
			return frappe.utils.to_title_case(key);
		});
}

/**
 * Turn an attrs object into escaped `key="value"` strings.
 * Attribute names become markup, so only normal-looking names are allowed;
 * on* attributes run their value as JavaScript, so they are never allowed —
 * bind handlers through the helper's own options instead.
 */
export function safe_attrs(attrs, component) {
	const escape = frappe.utils.escape_html;
	const out = [];
	for (const [key, value] of Object.entries(attrs || {})) {
		if (!/^[a-zA-Z][\w.:-]*$/.test(key) || /^on/i.test(key)) {
			console.warn(`frappe.ui.${component}: refusing unsafe attribute "${key}"`);
			continue;
		}
		out.push(value === true ? key : `${key}="${escape(value)}"`);
	}
	return out;
}

/** True for promises and other thenables (async options, submenus...). */
export function is_thenable(value) {
	return !!value && typeof value.then === "function";
}

/** A { group, options: [...] } section in a mixed options list. */
export function is_group(entry) {
	return entry && typeof entry === "object" && "group" in entry && Array.isArray(entry.options);
}

/**
 * Lucide icon markup for a row or trigger. Icon names end up inside an svg
 * `use` href, so only plain names pass; anything else warns and renders
 * nothing.
 */
export function icon_html(name, svg_class, component) {
	if (typeof name !== "string" || !/^[a-z0-9-]+$/i.test(name)) {
		console.warn(`frappe.ui.${component}: icons take a lucide icon name, got "${name}"`);
		return "";
	}
	return frappe.utils.icon(name, "sm", "", "", svg_class, true);
}
