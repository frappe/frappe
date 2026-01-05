<template>
	<div class="relative flex h-full w-full flex-col gap-1.5">
		<InputLabel v-if="label" :class="[required ? `after:text-red-600 after:content-['_*']` : '']">
			{{ label }}
		</InputLabel>
		<div v-if="actionButton" class="absolute bottom-1.5 right-1.5 z-10 flex gap-1">
			<Button
				@click="actionButton?.handler"
				variant="outline"
				:icon="actionButton.icon"
				:title="actionButton.label"
				:disabled="readonly"
			></Button>
		</div>
		<codemirror
			v-model="code"
			:extensions="extensions"
			:tab-size="2"
			:autofocus="autofocus"
			:indent-with-tab="true"
			:style="{ height: height, maxHeight: maxHeight }"
			:disabled="readonly"
			@ready="setEditorValue"
			@blur="emitEditorValue"
		/>

		<Button v-if="showSaveButton" variant="solid" @click="emit('save', code)" class="mt-3 w-full text-base">
			Save
		</Button>
		<ErrorMessage class="text-xs leading-4" v-if="errorMessage" :message="errorMessage" />
	</div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch } from "vue"
import { Button } from "frappe-ui"
import { Codemirror } from "vue-codemirror"
import {
	autocompletion,
	closeBrackets,
	type CompletionContext,
	type Completion,
} from "@codemirror/autocomplete"
import { LanguageSupport, indentService } from "@codemirror/language"
import { EditorView, keymap } from "@codemirror/view"
import { indentMore, indentLess } from "@codemirror/commands"
import { indentationMarkers } from "@replit/codemirror-indentation-markers"
import { tomorrow } from "thememirror"
import JSON5 from "json5"
import { isPrivateKey } from "@/utils/helpers"
import { normalizeCode } from "@/utils/code"
import { useSerializer } from "@/utils/useSerializer"

import InputLabel from "@/components/InputLabel.vue"

const props = withDefaults(
	defineProps<{
		language?: "json" | "javascript" | "html" | "css" | "python"
		modelValue?: string | object | Array<string | object> | null
		height?: string
		maxHeight?: string
		autofocus?: boolean
		showSaveButton?: boolean
		showLineNumbers?: boolean
		completions?: Function | null
		label?: string
		required?: boolean
		readonly?: boolean
		borderless?: boolean
		emitOnChange?: boolean
		actionButton?: {
			icon: string
			label: string
			handler: () => void
		}
	}>(),
	{
		language: "javascript",
		modelValue: null,
		height: "auto",
		maxHeight: "250px",
		showLineNumbers: true,
		completions: null,
		borderless: false,
		emitOnChange: false,
	},
)
const emit = defineEmits(["update:modelValue", "save"])
const { jsonReplacer, jsonToJs, parseObjectString } = useSerializer()

const code = ref<string>("")
const setEditorValue = () => {
	let value = props.modelValue ?? ""
	try {
		if (props.language === "json" || typeof value === "object") {
			value = JSON5.stringify(value, { replacer: jsonReplacer, space: 2, quote: '"' })
			value = normalizeCode(value)
		}
		code.value = value
	} catch (e) {
		console.log("Error while converting value to JSON", e)
		// do nothing
	}
}

const isValidObjectString = (text: string) => {
	const objString = text.trim()
	if (
		(objString.startsWith("{") && objString.endsWith("}")) ||
		(objString.startsWith("[") && objString.endsWith("]"))
	) {
		return true
	}
	return false
}

const errorMessage = ref("")
const emitEditorValue = () => {
	try {
		errorMessage.value = ""
		let value = code.value || ""
		if (value && !value.startsWith("{{")) {
			if (props.language === "json") {
				value = jsonToJs(value)
			} else if (props.language === "javascript" && isValidObjectString(value)) {
				value = parseObjectString(value)
			}
		}

		if (!props.showSaveButton && !props.readonly) {
			emit("update:modelValue", value)
		}
		return value
	} catch (e: any) {
		console.error("Error while parsing JSON for editor", e)
		errorMessage.value = `Invalid object/JSON: ${e.message}`
	}
}

const languageExtension = ref<LanguageSupport>()
const autocompleteExtension = ref()
const customCompletionsExtension = ref()

async function setLanguageExtension() {
	const importMap = {
		json: () => import("@codemirror/lang-json"),
		javascript: () => import("@codemirror/lang-javascript"),
		html: () => import("@codemirror/lang-html"),
		css: () => import("@codemirror/lang-css"),
		python: () => import("@codemirror/lang-python"),
	}

	const languageImport = importMap[props.language]
	if (!languageImport) return

	const module = await languageImport()
	languageExtension.value = (module as any)[props.language]()
	const languageData = (module as any)[`${props.language}Language`]

	if (props.completions) {
		autocompleteExtension.value = languageData.data.of({
			autocomplete: props.completions,
		})
	}

	if (props.language === "javascript") {
		const { scopeCompletionSource } = module as any
		const windowCompletionSource = scopeCompletionSource(window)
		customCompletionsExtension.value = languageData.data.of({
			autocomplete: (context: CompletionContext) => {
				const result = windowCompletionSource(context)
				if (result && result.options) {
					result.options = result.options.filter((option: Completion) => !isPrivateKey(option.label))
				}
				return result
			},
		})
	}
}

onMounted(async () => {
	await setLanguageExtension()
})

watch(
	() => props.language,
	async () => {
		await setLanguageExtension()
	},
	{ immediate: true },
)

watch(() => props.modelValue, setEditorValue)

// Emit on change if emitOnChange prop is true
watch(code, () => {
	if (props.emitOnChange && !props.readonly) {
		emitEditorValue()
	}
})

const customIndent = indentService.of((context: any, pos: number) => {
	/* helper to indent correctly inside objects because codemirror fails to do it for a bare object literal */
	let node = context.state.tree.resolveInner(pos, -1)
	const parentBlock = node.parent
	const getIndent = () => context.lineIndent(node.from, -1) + context.unit

	if (node.name === "{") {
		if (
			// Top-level ambiguous Block Statement
			parentBlock?.name === "Block" ||
			// Object Literal immediately inside an array or argument list
			(parentBlock?.name === "ObjectExpression" &&
				["ArrayExpression", "ArgList"].includes(parentBlock.parent?.name))
		) {
			// Treat it as a bare object literal at the top level
			return getIndent()
		}
	} else if (node.name === "[") {
		// indent inside an array
		if (parentBlock?.name === "ArrayExpression") {
			return getIndent()
		}
	}
	// Fall back to the default indentation logic
	return null
})

const extensions = computed(() => {
	const baseExtensions = [
		closeBrackets(),
		indentationMarkers(),
		props.showLineNumbers ? EditorView.lineWrapping : [],
		tomorrow,
		EditorView.theme({
			"&": {
				fontFamily: "monospace",
				fontSize: "12px",
			},
			".cm-gutters": {
				display: props.showLineNumbers ? "flex" : "none",
			},
			...(props.borderless && {
				"&.cm-editor": {
					border: "none !important",
					borderRadius: "0 !important",
				},
			}),
		}),
		EditorView.domEventHandlers({
			cut: (event, _view) => {
				event.stopPropagation()
			},
			copy: (event, _view) => {
				event.stopPropagation()
			},
			paste: (event, _view) => {
				event.stopPropagation()
			},
		}),
		keymap.of([
			{
				key: "Tab",
				run: indentMore,
				shift: indentLess,
			},
		]),
	]
	if (!props.readonly) {
		baseExtensions.push(
			keymap.of([
				{
					key: "Ctrl-s",
					mac: "Cmd-s",
					run: () => {
						emit("save", emitEditorValue())
						return true
					},
					stopPropagation: true,
				},
			]),
		)
	}
	if (languageExtension.value) {
		baseExtensions.unshift(languageExtension.value)
	}
	if (autocompleteExtension.value) {
		baseExtensions.push(autocompleteExtension.value)
	}
	if (customCompletionsExtension.value) {
		baseExtensions.push(customCompletionsExtension.value)
	}
	if (isObjectLiteral.value) {
		baseExtensions.push(customIndent)
	}
	const autocompletionOptions = {
		activateOnTyping: true,
		maxRenderedOptions: 10,
		closeOnBlur: false,
		icons: false,
		optionClass: () => "flex h-7 !px-2 items-center rounded !text-gray-600",
	}
	baseExtensions.push(autocompletion(autocompletionOptions))
	return baseExtensions
})

const isObjectLiteral = computed(
	() => props.language === "javascript" && typeof props.modelValue === "object",
)

defineExpose({
	errorMessage,
	emitEditorValue,
})
</script>
