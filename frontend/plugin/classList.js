// Writes every class name the built stylesheets define to `classes.json` beside them, so the
// server can tell a Client Script author which class has no rule.

import postcss from "postcss";

export const CLASS_LIST = "classes.json";

export default function classList() {
	return {
		name: "frappe-class-list",
		apply: "build",
		generateBundle(_options, bundle) {
			const names = new Set();
			for (const output of Object.values(bundle)) {
				if (output.type !== "asset" || !output.fileName.endsWith(".css")) continue;
				for (const name of classNames(Buffer.from(output.source).toString()))
					names.add(name);
			}
			this.emitFile({
				type: "asset",
				fileName: CLASS_LIST,
				source: JSON.stringify([...names].sort()),
			});
		},
	};
}

/** Every class in a stylesheet's selectors, unescaped, so `.hover\:p-3:hover` reads `hover:p-3`. */
export function classNames(css) {
	const names = new Set();
	postcss.parse(css).walkRules((rule) => {
		for (const [, escaped] of rule.selector.matchAll(CLASS)) names.add(unescape(escaped));
	});
	return [...names];
}

const CLASS = /\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[\w-])+)/g;

// A leading digit is written as its hex code plus a space; any other escape is the character itself.
function unescape(selector) {
	return selector
		.replace(/\\([0-9a-fA-F]{1,6}) ?/g, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
		.replace(/\\(.)/g, "$1");
}
