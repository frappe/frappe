/**
 * Add a database app's CSS files to the document as style elements.
 *
 * Keep the elements by file path across registry rebuilds, so an edit replaces a file's styles
 * instead of adding a copy.
 */

import { isEditor } from "@/utils/helpers"

const styleElements = new Map<string, HTMLStyleElement>()

export function injectAppStyle(path: string, source: string) {
	let element = styleElements.get(path)
	if (!element || !element.isConnected) {
		element = document.createElement("style")
		element.dataset.studioAppCss = path
		document.head.append(element)
		styleElements.set(path, element)
	}
	const css = fenceToCanvas(source)
	if (element.textContent !== css) element.textContent = css
}

export function clearAppStyles(keep: Set<string> = new Set()) {
	for (const [path, element] of styleElements) {
		if (keep.has(path)) continue
		element.remove()
		styleElements.delete(path)
	}
}

// A sheet's document roots, which in the editor mean the canvas copy of the page.
const DOCUMENT_ROOTS = /(^|[{},]|\*\/)(\s*)(?:html|body|:root)(?=[\s{,.:#[>+~])/g
// `@import` is only read at the top of a sheet, so it cannot move inside the fence.
const SHEET_AT_RULES = /@(?:charset|import)\b[^;]*;/gi

/** In the editor the app shares a document with the editor's own chrome, so fence it into the canvas. */
function fenceToCanvas(css: string): string {
	if (!isEditor()) return css
	const imports: string[] = []
	const rules = css.replace(SHEET_AT_RULES, (rule) => {
		imports.push(rule)
		return ""
	})
	return `${imports.join("\n")}\n@scope (.canvas) {\n${rules.replace(DOCUMENT_ROOTS, "$1$2:scope")}\n}`
}
