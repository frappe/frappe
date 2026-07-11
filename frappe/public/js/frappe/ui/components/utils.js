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
 * Refuse hrefs on schemes that run code — escaping can't make those safe.
 */
export function safe_href(href, component) {
	if (!href) return null;
	if (/^\s*(javascript|data|vbscript):/i.test(href)) {
		console.warn(`frappe.ui.${component}: refusing unsafe href "${href}"`);
		return null;
	}
	return href;
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
