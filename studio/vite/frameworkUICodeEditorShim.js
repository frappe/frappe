import fs from "fs"
import path from "path"

/**
 * Temporary: @framework/ui's CodeEditorField still imports CodeEditor/CodePreview from
 * frappe-ui/experimental, which frappe-ui deleted in 1.0.0-beta.74, so the studio build
 * fails. Until frappe/frappe#42965 lands, swap it for a stand-in built on
 * frappe-ui/code-editor. Checks the file itself, so the swap stops once frappe is fixed.
 * Delete this plugin and src/stubs/CodeEditorField.vue after that.
 */
export default function frameworkUICodeEditorShim(appsDir, frontendDir) {
	const field = path.resolve(appsDir, "frappe", "ui", "src", "components", "Fields", "CodeEditorField.vue")
	const stub = path.resolve(frontendDir, "src/stubs/CodeEditorField.vue")
	const isBroken = () => {
		try {
			return /\bCodeEditor\b[^;]*from\s+["']frappe-ui\/experimental["']/.test(fs.readFileSync(field, "utf8"))
		} catch {
			return false
		}
	}

	return {
		name: "studio:framework-ui-code-editor-shim",
		enforce: "pre",
		async resolveId(source, importer, options) {
			if (!importer || !source.endsWith("CodeEditorField.vue") || !isBroken()) return null
			const resolved = await this.resolve(source, importer, { ...options, skipSelf: true })
			return resolved?.id.split("?")[0] === field ? stub : null
		},
	}
}
