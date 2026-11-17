import assert from "node:assert/strict";
import test from "node:test";

import postcss from "postcss";
import tailwindcss from "tailwindcss";
import { build } from "vite";

import containerQueries from "../../container-queries.mjs";

for (const minify of [false, true]) {
	test(`island breakpoints follow the container with minify=${minify}`, async () => {
		const result = await build({
			configFile: false,
			envFile: false,
			publicDir: false,
			logLevel: "silent",
			css: {
				postcss: {
					plugins: [
						tailwindcss({
							content: [{ raw: "sm:block max-sm:hidden", extension: "html" }],
							corePlugins: { preflight: false },
						}),
					],
				},
			},
			plugins: [
				{
					name: "breakpoint-fixture",
					resolveId(id) {
						if (["virtual:entry", "virtual:breakpoints.css"].includes(id))
							return `\0${id}`;
					},
					load(id) {
						if (id === "\0virtual:entry")
							return 'import "virtual:breakpoints.css"; export const mount = () => {};';
						if (id === "\0virtual:breakpoints.css")
							return `
								@tailwind utilities;
								@media (max-width: 639px) { .maximum { display: flex; } }
								@media (max-width: 767px) and (pointer: coarse) { .touch { display: grid; } }
								@media (prefers-reduced-motion: reduce) { .motion { animation: none; } }
							`;
					},
				},
				containerQueries,
			],
			build: {
				write: false,
				minify,
				target: "esnext",
				cssCodeSplit: false,
				modulePreload: false,
				reportCompressedSize: false,
				rollupOptions: {
					input: "virtual:entry",
					preserveEntrySignatures: "exports-only",
				},
			},
		});

		const css = result.output.find((asset) => asset.fileName.endsWith(".css")).source;
		const conditions = new Map();
		postcss.parse(css).walkRules((rule) => conditions.set(rule.selector, rule.parent));
		for (const [selector, queries] of [
			[".sm\\:block", ["(min-width:640px)", "(width>=640px)"]],
			[".max-sm\\:hidden", ["not(min-width:640px)", "not(width>=640px)", "(width<640px)"]],
			[".maximum", ["(max-width:639px)", "(width<=639px)"]],
		]) {
			const rule = conditions.get(selector);
			assert.equal(rule?.name, "container", selector);
			assert.ok(queries.includes(rule.params.replace(/\s/g, "")), rule.params);
		}
		assert.equal(conditions.get(".touch")?.name, "media");
		assert.match(conditions.get(".touch").params, /pointer:\s*coarse/);
		assert.equal(conditions.get(".motion")?.name, "media");
		assert.match(conditions.get(".motion").params, /prefers-reduced-motion:\s*reduce/);
	});
}
