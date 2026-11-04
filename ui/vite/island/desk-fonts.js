// PostCSS plugin. It asks for the font families the host page registers.
//
// An island never loads frappe-ui's font stylesheet, so `InterVar` matches no
// registered face and the island renders in the system font. Desk registers the
// same typeface as `InterVariable` and `Inter`. `@font-face` is document-scoped,
// so those faces already reach the shadow tree. Only the name needs a rewrite.

/** Optionally quoted, and not the leading half of `InterVariable`. */
const FRAPPE_UI_FONT = /(["']?)InterVar\1(?![\w-])/g;

/** Variable file first, static weights as the fallback desk also registers. */
const DESK_FONTS = "InterVariable, Inter";

/** @type {import('postcss').Plugin} */
const deskFonts = {
	postcssPlugin: "island-desk-fonts",
	Declaration(decl) {
		if (!/font/i.test(decl.prop) || typeof decl.value !== "string") return;
		FRAPPE_UI_FONT.lastIndex = 0;
		decl.value = decl.value.replace(FRAPPE_UI_FONT, DESK_FONTS);
	},
};

export default deskFonts;
