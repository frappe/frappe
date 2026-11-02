// Monaco (VSCode's editor engine) with Vite's worker wiring. Import monaco from
// here so the worker environment is configured exactly once.
import * as monaco from "monaco-editor"
import editorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker"
import cssWorker from "monaco-editor/esm/vs/language/css/css.worker?worker"
import htmlWorker from "monaco-editor/esm/vs/language/html/html.worker?worker"
import jsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker"
import tsWorker from "monaco-editor/esm/vs/language/typescript/ts.worker?worker"

self.MonacoEnvironment = {
	getWorker(_, label) {
		if (label === "json") return new jsonWorker()
		if (["css", "scss", "less"].includes(label)) return new cssWorker()
		if (["html", "handlebars", "razor"].includes(label)) return new htmlWorker()
		if (["typescript", "javascript"].includes(label)) return new tsWorker()
		return new editorWorker()
	},
}

export { monaco }
