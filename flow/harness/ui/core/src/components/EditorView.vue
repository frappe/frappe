<template>
	<div class="flex min-h-0 flex-1 flex-col">
		<div class="flex h-11 flex-none items-center gap-2 border-b border-outline-gray-1 px-2.5">
			<Breadcrumbs v-if="activeTab" class="flow-crumbs min-w-0" :items="crumbs" />
			<span v-else class="text-[13.5px] text-ink-gray-5">/</span>
			<span class="flex-1" />
			<Button
				v-if="activeTab?.dirty"
				variant="ghost"
				size="sm"
				class="flex-none"
				title="Save (⌘S)"
				@click="save"
			>
				Save
			</Button>
			<Button
				v-if="diffRender"
				variant="outline"
				size="sm"
				class="flex-none"
				:title="diffSplit ? 'Unified view' : 'Split view'"
				@click="toggleDiffLayout"
			>
				<template #icon>
					<FeatherIcon :name="diffSplit ? 'align-justify' : 'columns'" class="h-4 w-4" />
				</template>
			</Button>
			<Button
				v-if="activeTab"
				variant="outline"
				size="sm"
				class="flex-none"
				:class="wrapText ? '!bg-surface-gray-3' : ''"
				:title="wrapText ? 'Disable word wrap' : 'Wrap text'"
				:aria-pressed="wrapText"
				icon="lucide-wrap-text"
				@click="toggleWrap"
			/>
			<Button
				variant="outline"
				size="sm"
				class="flex-none"
				:class="explorerOpen ? '!bg-surface-gray-3' : ''"
				:title="explorerOpen ? 'Hide files' : 'Show files'"
				:aria-pressed="explorerOpen"
				@click="explorerOpen = !explorerOpen"
			>
				<template #icon>
					<FeatherIcon name="folder" class="h-4 w-4" />
				</template>
			</Button>
		</div>

		<!-- the files bar opens below the header, beside the editor -->
		<div class="flex min-h-0 flex-1">
			<div class="flex min-w-0 flex-1 flex-col">
				<div
					v-if="!activeTab"
					class="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center"
				>
					<FeatherIcon name="file-text" class="h-6 w-6 text-ink-gray-3" />
					<span class="text-sm text-ink-gray-5">No file open</span>
					<span class="text-xs leading-5 text-ink-gray-4">
						{{
							workspace.view === "diff"
								? "Select a changed file to review its diff"
								: "Select a file to view or edit it"
						}}
					</span>
				</div>
				<div
					v-else-if="activeTab.error"
					class="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center"
				>
					<span class="text-xs text-ink-gray-5">{{ activeTab.error }}</span>
					<button
						class="flow-btn-secondary"
						@click="(activeTab.diff ? flow.openDiffFile : flow.openFile)(activeTab.path)"
					>
						Retry
					</button>
				</div>
				<LoadingState
					v-else-if="activeTab.content == null"
					class="flex-1 justify-center text-xs text-ink-gray-4"
				/>
				<div v-show="showEditorHost" ref="editorEl" class="min-h-0 flex-1" />
				<div v-show="showDiffHost" ref="diffEl" class="min-h-0 flex-1" />
			</div>

			<!-- shut with the panel too: its diff list polls while open -->
			<FilesBar :open="explorerOpen && workspace.open" :mode="barMode" />
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref, watch } from "vue"
import Breadcrumbs from "frappe-ui/src/components/Breadcrumbs/Breadcrumbs.vue"
import Button from "frappe-ui/src/components/Button/Button.vue"
import FeatherIcon from "./FeatherIcon.vue"

import { compactDisplayText } from "../transcript.js"
import FilesBar from "./FilesBar.vue"
import LoadingState from "./LoadingState.vue"

const flow = inject("flow")
const workspace = computed(() => flow.state.workspace)
const cwd = computed(() => flow.explorerCwd())
const activeTab = computed(
	() => workspace.value.tabs.find((tab) => tab.path === workspace.value.active) ?? null,
)

const crumbs = computed(() => {
	if (!activeTab.value) return []
	return compactDisplayText(activeTab.value.path, cwd.value)
		.split("/")
		.filter(Boolean)
		.map((label) => ({ label }))
})

// the right bar serves the active mode: the cwd tree, or the session's changed files
const explorerOpen = ref(false)
const barMode = computed(() =>
	(activeTab.value ? activeTab.value.diff : workspace.value.view === "diff") ? "diff" : "files",
)

// another chat's workspace shuts the bar; a files or diff view (menu or restore) opens it
watch(
	() => [workspace.value, workspace.value.open, workspace.value.active, workspace.value.view],
	([ws, open, active, view], previous) => {
		if (ws !== previous?.[0]) explorerOpen.value = false
		if (open && !active && (view === "files" || view === "diff")) explorerOpen.value = true
	},
	{ immediate: true },
)

// Monaco objects stay out of Vue's reactivity: one editor, one model per tab.
// Models hold unsaved edits, so they live as long as their tab. The library
// loads lazily on first open, so the chat page never pays for the editor
// bundle up front.
const editorEl = ref(null)
const diffEl = ref(null)
let monaco = null
let editor = null
let diffEditor = null
const models = new Map()
const diffModels = new Map() // path -> original-side model, diff tabs only

const EDITOR_OPTIONS = {
	automaticLayout: true,
	fontSize: 13.5,
	lineHeight: 23,
	padding: { top: 12, bottom: 12 },
	cursorBlinking: "smooth",
	minimap: { enabled: false },
	scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10 },
	overviewRulerLanes: 0,
	hideCursorInOverviewRuler: true,
	scrollBeyondLastLine: false,
	fixedOverflowWidgets: true,
}

const contentReady = computed(
	() => !!activeTab.value && !activeTab.value.error && activeTab.value.content != null,
)
// a diff tab whose original is empty is a new or untracked file: render it as
// a plain file (whole-file-green adds nothing) while the bar stays in diff mode
const diffRender = computed(() => !!activeTab.value?.diff && !!activeTab.value?.original)
const showEditorHost = computed(() => contentReady.value && !diffRender.value)
const showDiffHost = computed(() => contentReady.value && diffRender.value)

const diffSplit = ref(false) // unified by default: the panel is narrow
function toggleDiffLayout() {
	diffSplit.value = !diffSplit.value
	diffEditor?.updateOptions({ renderSideBySide: diffSplit.value })
}

const wrapText = ref(false)
const wrapValue = () => (wrapText.value ? "on" : "off")
function toggleWrap() {
	wrapText.value = !wrapText.value
	const wordWrap = wrapValue()
	editor?.updateOptions({ wordWrap })
	// diffWordWrap governs the diff editor's inner editors ("inherit" tracks wordWrap)
	diffEditor?.updateOptions({ wordWrap, diffWordWrap: wordWrap })
}

// Floating "Add to chat" pill over a non-empty selection: queues a file+lines
// reference for the composer (never the selected text itself).
function wireAddToChat(ed) {
	const node = document.createElement("button")
	node.type = "button"
	node.className = "flow-add-to-chat"
	node.textContent = "Add to chat"
	node.addEventListener("mousedown", (e) => e.preventDefault()) // keep the selection
	let position = null
	const widget = {
		getId: () => "flow.add-to-chat",
		allowEditorOverflow: true, // never clipped by the scrolled viewport
		getDomNode: () => node,
		getPosition: () =>
			position && {
				position,
				preference: [
					monaco.editor.ContentWidgetPositionPreference.ABOVE,
					monaco.editor.ContentWidgetPositionPreference.BELOW,
				],
			},
	}
	node.addEventListener("click", () => {
		const sel = ed.getSelection()
		const tab = activeTab.value
		if (!tab || !sel || sel.isEmpty()) return
		let end = sel.endLineNumber
		if (end > sel.startLineNumber && sel.endColumn === 1) end-- // drag past the newline
		flow.addCodeRef(tab.path, sel.startLineNumber, end)
		position = null
		ed.layoutContentWidget(widget)
	})
	ed.onDidChangeCursorSelection((e) => {
		position = e.selection.isEmpty()
			? null
			: { lineNumber: e.selection.startLineNumber, column: e.selection.startColumn }
		ed.layoutContentWidget(widget)
	})
	ed.addContentWidget(widget)
}

// monaco infers the language from the file uri; only fill its gaps
const LANG_OVERRIDES = { vue: "html", svelte: "html" }

function modelFor(tab) {
	let model = models.get(tab.path)
	if (!model) {
		const ext = tab.name.split(".").pop()?.toLowerCase()
		model = monaco.editor.createModel(tab.content ?? "", LANG_OVERRIDES[ext], monaco.Uri.file(tab.path))
		// Dirty tracking via version ids: O(1) per keystroke (never a full-text
		// compare), and undoing back to the saved state reads as clean again.
		let savedVersion = model.getAlternativeVersionId()
		model.flowMarkSaved = (version = model.getAlternativeVersionId()) => (savedVersion = version)
		model.onDidChangeContent(() =>
			flow.markFileDirty(tab.path, model.getAlternativeVersionId() !== savedVersion),
		)
		models.set(tab.path, model)
	}
	return model
}

function syncModel() {
	const tab = activeTab.value
	if (!tab || tab.content == null) return
	if (diffRender.value) {
		if (!diffEditor) return
		const model = modelFor(tab)
		let original = diffModels.get(tab.path)
		if (!original) {
			original = monaco.editor.createModel(tab.original ?? "", model.getLanguageId())
			diffModels.set(tab.path, original)
		} else if (original.getValue() !== (tab.original ?? "")) {
			original.setValue(tab.original ?? "")
		}
		const current = diffEditor.getModel()
		if (current?.modified !== model || current?.original !== original)
			diffEditor.setModel({ original, modified: model })
	} else {
		if (!editor) return
		const model = modelFor(tab)
		if (editor.getModel() !== model) editor.setModel(model)
	}
}

// Gate on `open` and on a tab actually needing this editor kind: the closed
// panel stays mounted for the slide animation and must not pull the monaco
// bundle (or build an editor) until it is actually shown.
watch([editorEl, () => workspace.value.open, showEditorHost], async ([el, open, needed]) => {
	if (el && open && needed && !editor) {
		monaco ??= (await import("../monaco.js")).monaco
		if (!editorEl.value || !workspace.value.open || editor) return // closed while loading
		editor = monaco.editor.create(editorEl.value, {
			...EDITOR_OPTIONS,
			wordWrap: wrapValue(),
		})
		applyTheme()
		editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, save)
		wireAddToChat(editor)
		syncModel()
	} else if (!el && editor) {
		editor.dispose()
		editor = null
	}
})

// the diff twin: same lifecycle, whole-file view with the session's changes
watch([diffEl, () => workspace.value.open, showDiffHost], async ([el, open, needed]) => {
	if (el && open && needed && !diffEditor) {
		monaco ??= (await import("../monaco.js")).monaco
		if (!diffEl.value || !workspace.value.open || diffEditor) return
		diffEditor = monaco.editor.createDiffEditor(diffEl.value, {
			...EDITOR_OPTIONS,
			wordWrap: wrapValue(),
			diffWordWrap: wrapValue(),
			renderSideBySide: diffSplit.value,
			useInlineViewWhenSpaceIsLimited: false,
			hideUnchangedRegions: { enabled: false },
			// the revert-arrows gutter: dead space here, and it picks up a stray
			// focus outline (its div shares the .monaco-editor class)
			renderGutterMenu: false,
			// the overview ruler's draggable viewport handle is the diff scrollbar;
			// the editors' own slider beside it would read as a second one
			scrollbar: { vertical: "hidden", verticalScrollbarSize: 0, horizontalScrollbarSize: 10 },
		})
		applyTheme()
		diffEditor.getModifiedEditor().addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, save)
		wireAddToChat(diffEditor.getModifiedEditor())
		syncModel()
	} else if (!el && diffEditor) {
		diffEditor.dispose()
		diffEditor = null
	}
})

watch(
	[
		() => activeTab.value?.path,
		() => activeTab.value?.content != null,
		() => activeTab.value?.diff,
		() => activeTab.value?.original,
	],
	syncModel,
)

// a refetch (TurnFiles click, retry) refreshed the baseline; mirror it into a
// clean model — dirty models keep the user's edits
watch(
	() => activeTab.value?.content,
	(content) => {
		const tab = activeTab.value
		if (!tab || content == null) return
		const model = models.get(tab.path)
		if (model && !tab.dirty && model.getValue() !== content) {
			model.setValue(content)
			model.flowMarkSaved()
			flow.markFileDirty(tab.path, false)
		}
	},
)

// dispose models whose tab is gone (close, session switch)
watch(
	() => workspace.value.tabs.map((tab) => tab.path).join("\n"),
	() => {
		const alive = new Set(workspace.value.tabs.map((tab) => tab.path))
		for (const [path, model] of models) {
			if (alive.has(path)) continue
			if (editor?.getModel() === model) editor.setModel(null)
			if (diffEditor?.getModel()?.modified === model) diffEditor.setModel(null)
			model.dispose()
			models.delete(path)
		}
		for (const [path, model] of diffModels) {
			if (alive.has(path)) continue
			if (diffEditor?.getModel()?.original === model) diffEditor.setModel(null)
			model.dispose()
			diffModels.delete(path)
		}
	},
)

// Editor theme derived from the app's frappe-ui tokens: the panel surface as
// background and the app's ink color for the cursor. Redefined on every toggle
// because the CSS variables change with [data-theme].
function cssColor(name) {
	const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
	if (raw.startsWith("#")) return raw
	const match = raw.match(/^rgba?\(([^)]+)\)/)
	if (!match) return null
	const [r, g, b] = match[1].split(/[\s,/]+/).map(Number)
	if ([r, g, b].some((v) => !Number.isFinite(v))) return null
	return "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")
}

function translucent(name, alpha) {
	const hex = cssColor(name)
	return hex && hex + alpha
}

function applyTheme() {
	if (!monaco) return
	const dark = document.documentElement.getAttribute("data-theme") === "dark"
	const name = dark ? "flow-dark" : "flow-light"
	const colors = {
		focusBorder: "#00000000",
		"editor.background": cssColor("--surface-base"),
		"editorCursor.foreground": cssColor("--ink-gray-9"),
		"editor.lineHighlightBackground": cssColor("--surface-gray-1"),
		// translucent sliders (VSCode-style): diff highlights and ruler marks
		// stay visible through the scrollbar instead of being covered by it
		"scrollbarSlider.background": translucent("--ink-gray-4", "66"),
		"scrollbarSlider.hoverBackground": translucent("--ink-gray-5", "99"),
		"scrollbarSlider.activeBackground": translucent("--ink-gray-5", "99"),
	}
	monaco.editor.defineTheme(name, {
		base: dark ? "vs-dark" : "vs",
		inherit: true,
		rules: [],
		colors: Object.fromEntries(Object.entries(colors).filter(([, value]) => value)),
	})
	monaco.editor.setTheme(name)
}

// frappe-ui's useColorScheme owns data-theme; follow it instead of the store
const themeObserver = new MutationObserver(applyTheme)
themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] })

onBeforeUnmount(() => {
	themeObserver.disconnect()
	editor?.dispose()
	editor = null
	diffEditor?.dispose()
	diffEditor = null
	for (const model of models.values()) model.dispose()
	models.clear()
	for (const model of diffModels.values()) model.dispose()
	diffModels.clear()
})

async function save() {
	const tab = activeTab.value
	const model = tab && models.get(tab.path)
	if (!tab || !model) return
	// snapshot version and text together; edits made while the save is in
	// flight stay marked dirty afterwards
	const version = model.getAlternativeVersionId()
	if (!(await flow.saveFile(tab.path, model.getValue()))) return
	model.flowMarkSaved(version)
	flow.markFileDirty(tab.path, model.getAlternativeVersionId() !== version)
}
</script>

<style scoped>
/* Breadcrumbs ships header-scale type; fit it to the path row */
.flow-crumbs :deep(button) {
	font-size: 13.5px;
	font-weight: 420;
	padding-top: 0;
	padding-bottom: 0;
	cursor: default;
}
.flow-crumbs :deep(span[aria-hidden="true"]) {
	font-size: 13.5px;
}
</style>
