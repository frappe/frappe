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
					<LucideIcon :name="tool.icon" class="h-3 w-3" />
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
import LucideIcon from "@/components/LucideIcon.vue"
import { useDark } from "@vueuse/core"
import { marked } from "marked"
import ace from "ace-builds"
import "ace-builds/src-min-noconflict/mode-markdown"
import "ace-builds/src-min-noconflict/theme-chrome"
import "ace-builds/src-min-noconflict/theme-twilight"

const props = withDefaults(
	defineProps<{
		label?: string
		modelValue: string
		showPreview?: boolean
	}>(),
	{
		modelValue: "",
		showPreview: false,
	},
)

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
	{ id: "bold", icon: "Bold", title: "Bold", prefix: "**", suffix: "**", shortcut: "Ctrl+B" },
	{ id: "italic", icon: "Italic", title: "Italic", prefix: "_", suffix: "_", shortcut: "Ctrl+I" },
	{ id: "h1", icon: "Heading1", title: "Heading 1", prefix: "# ", suffix: "", shortcut: "Ctrl+1" },
	{ id: "h2", icon: "Heading2", title: "Heading 2", prefix: "## ", suffix: "", shortcut: "Ctrl+2" },
	{ id: "h3", icon: "Heading3", title: "Heading 3", prefix: "### ", suffix: "", shortcut: "Ctrl+3" },
	{ id: "quote", icon: "Quote", title: "Quote", prefix: "> ", suffix: "", shortcut: "Ctrl+Q" },
	{ id: "code", icon: "Code", title: "Code Block", prefix: "```\n", suffix: "\n```", shortcut: "Ctrl+K" },
	{ id: "link", icon: "Link", title: "Link", prefix: "[", suffix: "](url)", shortcut: "Ctrl+L" },
	{ id: "image", icon: "Image", title: "Image", prefix: "![", suffix: "](url)", shortcut: "Ctrl+P" },
	{ id: "list", icon: "List", title: "List", prefix: "- ", suffix: "", shortcut: "Ctrl+U" },
	{ id: "olist", icon: "ListOrdered", title: "Numbered List", prefix: "1. ", suffix: "", shortcut: "Ctrl+O" },
	{ id: "hr", icon: "Minus", title: "Horizontal Rule", prefix: "\n---\n", suffix: "", shortcut: "Ctrl+R" },
	{ id: "br", icon: "CornerDownLeft", title: "Line Break", prefix: "", suffix: "", shortcut: "Ctrl+Enter" },
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

	// Handle the special case for the line break (Ctrl+Enter)
	if (tool.id === "br") {
		newText = "\n<br>"
	} else if (tool.id === "link" && !selectedText) {
		newText = "[Link text](url)"
	} else {
		if (selectedText) {
			newText = tool.prefix + selectedText + tool.suffix
		} else {
			newText = tool.prefix + "text" + tool.suffix
		}
	}

	// Replace the selected text (or insert new text)
	session.replace(range, newText)
	editor.value.focus()

	// Handle cursor positioning after insertion
	if (newText === "\n<br>") {
		const cursorPos = selection.getCursor()
		selection.moveCursorTo(cursorPos.row + 1, 0) // Move to the next line
	} else if (!selectedText) {
		// If no text was selected, select the inserted text (for styling purposes)
		const startCol = range.start.column + tool.prefix.length
		const endCol = startCol + 4
		selection.setSelectionRange({
			start: { row: range.start.row, column: startCol },
			end: { row: range.start.row, column: endCol },
		})
	}
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
