/**
 * PostCSS plugin: stamp !important on every declaration that lives inside
 * a `[data-frappe-ui]` selector.
 *
 * Why this is needed
 * ------------------
 * desk.bundle.css (Bootstrap helpers layer) uses `!important` on ~181
 * utility-name rules such as `.pt-5 { padding-top: 42px !important }`.
 * Within the CSS !important origin, specificity is re-evaluated normally.
 * Our scoped rules have specificity 0,2,0 (attribute + class) vs. Bootstrap's
 * 0,1,0 (class only), so adding `!important` here lets our rules win.
 *
 * The guard `!decl.important` prevents double-stamping when processing the
 * pre-built frappe-ui CSS (which already has !important from its own Vite
 * build step).
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
