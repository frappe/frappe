// PostCSS plugin. It retargets document-level selectors at the shadow host, so
// the tokens and type styles they carry reach an island. A shadow root inherits
// from `:host`, and nothing inside one matches `:root`, `html` or `body`.

const DOCUMENT_ROOTS = /(^|,)\s*(:root|html|body)\b/g;

/** @type {import('postcss').Plugin} */
const rootToHost = {
	postcssPlugin: "island-root-to-host",
	Rule(rule) {
		if (typeof rule.selector !== "string") return;
		// Leading position only. `body .foo` is a real descendant selector,
		// but `.foo body` matches nothing a rewrite would fix.
		rule.selector = rule.selector.replace(DOCUMENT_ROOTS, "$1:host");
	},
};

export default rootToHost;
