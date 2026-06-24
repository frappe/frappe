<template>
	<div class="group relative flex h-full w-full flex-col gap-1.5">
		<template v-if="label">
			<FormInputLabel v-if="isFormInput">{{ label }}</FormInputLabel>
			<InputLabel v-else :class="[required ? `after:text-ink-red-7 after:content-['_*']` : '']">
				{{ label }}
			</InputLabel>
		</template>
		<div v-if="actionButton" class="absolute bottom-[3px] right-[3px] z-10 flex gap-1">
			<Button
				@click="actionButton?.handler"
				variant="subtle"
				class="h-2 w-2 rounded-sm text-ink-gray-3 opacity-0 transition-opacity group-hover:opacity-100"
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
			@ready="onEditorReady"
			@blur="syncToParent"
		/>

		<span class="text-p-xs text-ink-gray-6" v-show="description" v-html="description"></span>
		<Button
			v-if="showSaveButton"
			variant="solid"
			@click="emit('save', syncToParent())"
			class="mt-3 w-full text-base"
		>
			Save
		</Button>
		<ErrorMessage class="text-xs leading-4" v-if="errorMessage" :message="errorMessage" />
	</div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue"
import { Button, ErrorMessage } from "frappe-ui"
import { Codemirror } from "vue-codemirror"
import {
	autocompletion,
	closeBrackets,
	type CompletionContext,
	type Completion,
	type CompletionSource,
} from "@codemirror/autocomplete"
import { Compartment, Extension } from "@codemirror/state"
import { indentService, indentUnit, LRLanguage } from "@codemirror/language"
import { EditorView, keymap } from "@codemirror/view"
import { indentMore, indentLess } from "@codemirror/commands"
import { indentationMarkers } from "@replit/codemirror-indentation-markers"
import { tomorrow } from "thememirror"
import JSON5 from "json5"
import { isPrivateKey } from "@/utils/helpers"
import { normalizeCode } from "@/utils/code"
import { jsonReplacer, parseObjectString } from "@/utils/serializer"

import InputLabel from "@/components/InputLabel.vue"
import FormInputLabel from "@/components/FormInputLabel.vue"

const props = withDefaults(
	defineProps<{
		language?: "json" | "javascript" | "html" | "css" | "vue"
		modelValue?: string | object | Array<string | object> | null
		height?: string
		maxHeight?: string
		autofocus?: boolean
		showSaveButton?: boolean
		showLineNumbers?: boolean
		completions?: Function | null
		label?: string
		description?: string
		required?: boolean
		readonly?: boolean
		borderless?: boolean
		emitOnChange?: boolean
		actionButton?: {
			icon: string
			label: string
			handler: () => void
		}
		isFormInput?: boolean
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

const code = ref<string>("")
const editorView = ref<EditorView | null>(null)

// -- Syncing --
const syncToEditor = () => {
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

const errorMessage = ref("")
const syncToParent = () => {
	try {
		errorMessage.value = ""
		let value = code.value || ""
		if (value && !value.startsWith("{{")) {
			if (props.language === "json") {
				value = JSON.parse(value)
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

// -- Language Extension --
let languageConf = new Compartment()
const loadLanguage = async (type: string): Promise<Extension> => {
	// The user-provided completion source (page-script bindings, etc.), scoped to a sublanguage.
	const customCompletions = (language: LRLanguage) => {
		if (!props.completions) return []
		return language.data.of({ autocomplete: props.completions })
	}

	// Completions inside a <script>/JS region: the custom source plus window globals (private keys
	// filtered out), keyed to the JS sublanguage so they don't fire in the surrounding template.
	const scriptCompletions = (javascriptLanguage: LRLanguage, windowScopeSource: CompletionSource) => [
		customCompletions(javascriptLanguage),
		javascriptLanguage.data.of({
			autocomplete: async (context: CompletionContext) => {
				const result = await windowScopeSource(context)
				if (result?.options) {
					result.options = result.options.filter((option: Completion) => !isPrivateKey(option.label))
				}
				return result
			},
		}),
	]

	switch (type) {
		case "javascript": {
			const { javascript, javascriptLanguage, scopeCompletionSource } = await import(
				"@codemirror/lang-javascript"
			)
			return [javascript(), ...scriptCompletions(javascriptLanguage, scopeCompletionSource(window))]
		}
		case "html": {
			const { html, htmlLanguage } = await import("@codemirror/lang-html")
			return [html(), customCompletions(htmlLanguage)]
		}
		case "css": {
			const { css } = await import("@codemirror/lang-css")
			return css()
		}
		case "json": {
			const { json } = await import("@codemirror/lang-json")
			return json()
		}
		case "vue": {
			const { vue } = await import("@codemirror/lang-vue")
			const { javascript, javascriptLanguage, scopeCompletionSource } = await import(
				"@codemirror/lang-javascript"
			)
			return [
				vue(),
				javascript().support,
				...scriptCompletions(javascriptLanguage, scopeCompletionSource(window)),
			]
		}
		default:
			return []
	}
}

async function updateLanguage() {
	const languageExtension = await loadLanguage(props.language)
	editorView.value?.dispatch({ effects: languageConf.reconfigure(languageExtension) })
}

// -- Editor Events --
const onEditorReady = (view: { view: EditorView }) => {
	editorView.value = view.view
	syncToEditor()
	updateLanguage()
}

watch(() => props.modelValue, syncToEditor)
watch(() => props.language, updateLanguage)
watch(code, () => {
	if (props.emitOnChange && !props.readonly) {
		syncToParent()
	}
})

// -- Extensions --
const extensions = computed(() => {
	const baseExtensions = [
		languageConf.of([]),
		indentUnit.of("\t"),
		closeBrackets(),
		indentationMarkers(),
		getAutocompletionOptions(),
		props.showLineNumbers ? EditorView.lineWrapping : [],
		isObjectLiteral.value ? customIndent : [],
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
		keymap.of([{ key: "Tab", run: indentMore, shift: indentLess }]),
	]
	if (!props.readonly) {
		baseExtensions.push(
			keymap.of([
				{
					key: "Ctrl-s",
					mac: "Cmd-s",
					run: () => {
						emit("save", syncToParent())
						return true
					},
					stopPropagation: true,
				},
			]),
		)
	}
	return baseExtensions
})

const getAutocompletionOptions = () => {
	return autocompletion({
		activateOnTyping: true,
		maxRenderedOptions: 10,
		closeOnBlur: false,
		icons: false,
		optionClass: () => "flex h-7 !px-2 items-center rounded !text-ink-gray-5",
	})
}

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

// -- Helpers --
const isObjectLiteral = computed(
	() => props.language === "javascript" && typeof props.modelValue === "object",
)

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

defineExpose({
	errorMessage,
	emitEditorValue: syncToParent,
})
</script>
