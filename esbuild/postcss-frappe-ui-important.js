/**
 * PostCSS plugin: stamp !important on every declaration that lives inside
 * a `[data-frappe-ui]` selector.
 *
 * Why this is needed
 * ------------------
 * `desk.bundle.css` (the Bootstrap helpers layer that powers traditional
 * Desk pages) declares ~181 utility rules like
 *   `.pt-5 { padding-top: 42px !important }`.
 * Within the CSS !important origin, specificity is re-evaluated normally.
 * Our scoped rules sit at specificity 0,2,0 (attribute + class) vs.
 * Bootstrap's 0,1,0 (class only), so stamping `!important` here lets the
 * scoped rules win the override battle when both layers fight over the
 * same property on an element that lives inside a `[data-frappe-ui]`
 * island.
 *
 * The `!decl.important` guard prevents double-stamping when a declaration
 * is already marked important (e.g. user-authored `!important` rules in
 * bundle CSS).
 *
 * Plays alongside:
 *   • tailwind.config.desk-islands.mjs (`important: '[data-frappe-ui]'`)
 *     which is what generates the `[data-frappe-ui]` ancestor selector
 *     on every Tailwind utility in the first place.
 *   • frappe-ui-scoped-preflight.css (manual `[data-frappe-ui]`-scoped
 *     equivalent of Tailwind's global preflight; rules in there are NOT
 *     stamped !important because they're meant to be overridable by
 *     utility classes).
 */

/** @type {import('postcss').Plugin} */
const frappeUIImportant = {
	postcssPlugin: "frappe-ui-important",
	Declaration(decl) {
		const rule = decl.parent;
		if (
			rule &&
			rule.type === "rule" &&
			typeof rule.selector === "string" &&
			rule.selector.includes("[data-frappe-ui]") &&
			!decl.important
		) {
			decl.important = true;
		}
	},
};

// Plain PostCSS 8 object-style plugin — DO NOT set .postcss = true here.
// That marker is only valid on factory *functions*; setting it on a plain
// object makes PostCSS try to call the object as a function, which throws.

module.exports = frappeUIImportant;
