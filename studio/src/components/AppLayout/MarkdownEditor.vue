<template>
	<div class="flex flex-col">
		<div v-if="label" class="mb-1.5 text-xs text-gray-600">{{ label }}</div>
		<div class="flex h-auto min-h-40 flex-col overflow-hidden rounded-lg border border-gray-200">
			<div class="flex gap-2 border-b border-gray-200 bg-gray-50 p-2">
				<Button
					v-for="tool in tools"
					:key="tool.id"
					variant="ghost"
					size="sm"
					@click="applyFormat(tool)"
					:title="`${tool.title} ${tool.shortcut ? `(${tool.shortcut})` : ''}`"
				>
					<component :is="tool.icon" class="h-3 w-3" />
				</Button>
			</div>

			<div class="flex flex-1">
				<div ref="editorContainer" class="flex-1"></div>
				<div v-if="showPreview" class="flex-1 overflow-y-auto border-l border-gray-200 p-4">
					<span v-html="compiledMarkdown"></span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from "vue"
import { useDark } from "@vueuse/core"
import { marked } from "marked"
import ace from "ace-builds"
import "ace-builds/src-min-noconflict/mode-markdown"
import "ace-builds/src-min-noconflict/theme-chrome"
import "ace-builds/src-min-noconflict/theme-twilight"

import LucideBold from "~icons/lucide/bold"
import LucideItalic from "~icons/lucide/italic"
import LucideHeading1 from "~icons/lucide/heading-1"
import LucideHeading2 from "~icons/lucide/heading-2"
import LucideHeading3 from "~icons/lucide/heading-3"
import LucideQuote from "~icons/lucide/quote"
import LucideCode from "~icons/lucide/code"
import LucideLink from "~icons/lucide/link"
import LucideImage from "~icons/lucide/image"
import LucideList from "~icons/lucide/list"
import LucideListOrdered from "~icons/lucide/list-ordered"
import LucideMinus from "~icons/lucide/minus"
import LucideCornerDownLeft from "~icons/lucide/corner-down-left"

import type { MarkdownEditorProps } from "@/types/studio_components/MarkdownEditor"

const props = withDefaults(defineProps<MarkdownEditorProps>(), {
	modelValue: "",
	showPreview: false,
})

const isDark = useDark()
const emit = defineEmits(["update:modelValue"])

const editor = ref<ace.Ace.Editor | null>(null)
const editorContainer = ref<HTMLElement | null>(null)
const content = ref(props.modelValue)

type Tool = {
	id: string
	icon: string
	title: string
	prefix: string
	suffix: string
	shortcut: string
}
const tools = ref<Tool[]>([
	{ id: "bold", icon: LucideBold, title: "Bold", prefix: "**", suffix: "**", shortcut: "Ctrl+B" },
	{ id: "italic", icon: LucideItalic, title: "Italic", prefix: "_", suffix: "_", shortcut: "Ctrl+I" },
	{ id: "h1", icon: LucideHeading1, title: "Heading 1", prefix: "# ", suffix: "", shortcut: "Ctrl+1" },
	{ id: "h2", icon: LucideHeading2, title: "Heading 2", prefix: "## ", suffix: "", shortcut: "Ctrl+2" },
	{ id: "h3", icon: LucideHeading3, title: "Heading 3", prefix: "### ", suffix: "", shortcut: "Ctrl+3" },
	{ id: "quote", icon: LucideQuote, title: "Quote", prefix: "> ", suffix: "", shortcut: "Ctrl+Q" },
	{ id: "code", icon: LucideCode, title: "Code Block", prefix: "```\n", suffix: "\n```", shortcut: "Ctrl+K" },
	{ id: "link", icon: LucideLink, title: "Link", prefix: "[", suffix: "](url)", shortcut: "Ctrl+L" },
	{ id: "image", icon: LucideImage, title: "Image", prefix: "![", suffix: "](url)", shortcut: "Ctrl+P" },
	{ id: "list", icon: LucideList, title: "List", prefix: "- ", suffix: "", shortcut: "Ctrl+U" },
	{
		id: "olist",
		icon: LucideListOrdered,
		title: "Numbered List",
		prefix: "1. ",
		suffix: "",
		shortcut: "Ctrl+O",
	},
	{
		id: "hr",
		icon: LucideMinus,
		title: "Horizontal Rule",
		prefix: "\n---\n",
		suffix: "",
		shortcut: "Ctrl+R",
	},
	{
		id: "br",
		icon: LucideCornerDownLeft,
		title: "Line Break",
		prefix: "",
		suffix: "",
		shortcut: "Ctrl+Enter",
	},
])

const compiledMarkdown = computed(() => {
	marked.setOptions({
		gfm: false,
	})
	return marked(content.value)
})

const applyFormat = (tool: Tool) => {
	if (!editor.value) return
	const session = editor.value.getSession()
	const selection = editor.value.getSelection()
	const range = selection.getRange()
	const selectedText = session.getTextRange(range)

	let newText
	let cursorOffset = 0

	if (tool.id === "br") {
		newText = "\n<br>"
		cursorOffset = 0
	} else if (tool.id === "link" && !selectedText) {
		newText = "[Link text](url)"
		cursorOffset = -5 // 5 characters back from the end: "(url)"
	} else {
		if (selectedText) {
			newText = tool.prefix + selectedText + tool.suffix
			cursorOffset = 0
		} else {
			newText = tool.prefix + "text" + tool.suffix
			cursorOffset = -tool.suffix.length
		}
	}

	session.replace(range, newText)
	editor.value.focus()

	// Handle cursor positioning after insertion
	if (newText === "\n<br>") {
		const cursorPos = selection.getCursor()
		selection.moveCursorTo(cursorPos.row + 1, 0)
	} else {
		const endPosition = session.doc.createAnchor(
			range.start.row,
			range.start.column + newText.length + cursorOffset,
		)
		selection.setSelectionAnchor(endPosition.row, endPosition.column)
		selection.clearSelection()
	}
	editor.value.scrollToLine(selection.getCursor().row, true, true)
}

const setupShortcuts = () => {
	tools.value.forEach((tool) => {
		if (tool.shortcut) {
			editor.value?.commands.addCommand({
				name: tool.id,
				bindKey: { win: tool.shortcut, mac: tool.shortcut.replace("Ctrl", "Cmd") },
				exec: () => applyFormat(tool),
			})
		}
	})
}

const handleResize = () => {
	editor.value?.resize()
}

watch(
	() => props.modelValue,
	(newVal) => {
		if (newVal !== editor.value?.getValue()) {
			editor.value?.setValue(newVal, -1)
		}
	},
)

watch(isDark, () => {
	editor.value?.setTheme(isDark.value ? "ace/theme/twilight" : "ace/theme/chrome")
})

function resetEditor(value: string) {
	value = props.modelValue
	editor.value?.setValue(value)
	editor.value?.clearSelection()
	editor.value?.setTheme(isDark.value ? "ace/theme/twilight" : "ace/theme/chrome")
}

watch(
	() => props.modelValue,
	(newValue) => {
		if (newValue !== editor.value?.getValue()) {
			resetEditor(props.modelValue as string)
		}
	},
)

onMounted(() => {
	editor.value = ace.edit(editorContainer.value as HTMLElement, {
		mode: "ace/mode/markdown",
		theme: isDark.value ? "ace/theme/twilight" : "ace/theme/chrome",
		fontSize: 14,
		wrap: true,
		showPrintMargin: false,
		highlightActiveLine: true,
	})
	resetEditor(props.modelValue)

	content.value = editor.value.getValue() || ""
	editor.value.on("change", () => {
		content.value = editor.value?.getValue() || ""
	})

	editor.value.on("blur", () => {
		emit("update:modelValue", content.value)
	})

	setupShortcuts()
	window.addEventListener("resize", handleResize)
})
</script>
