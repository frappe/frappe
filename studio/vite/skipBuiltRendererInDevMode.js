// renderer.html puts the built <script> in a Jinja else-branch so a developer-mode site loads
// only the dev server's renderer. Vite's build moves that script into <head>, outside the
// branch, so both renderers booted. Put the condition back around the moved tag.
const builtRendererScript = /<script type="module"[^>]*src="[^"]*\/renderer-[^"]*\.js"[^>]*><\/script>/

export default function skipBuiltRendererInDevMode() {
	return {
		name: "studio:skip-built-renderer-in-dev-mode",
		apply: "build",
		transformIndexHtml: {
			order: "post",
			handler(html, { filename }) {
				if (!filename.endsWith("renderer.html")) return html
				if (!builtRendererScript.test(html))
					throw new Error("renderer.html: built renderer script tag not found")
				return html.replace(builtRendererScript, (tag) => `{% if not is_developer_mode %}${tag}{% endif %}`)
			},
		},
	}
}
