<template>
	<div class="flex h-full flex-col gap-1.5">
		<codemirror
			v-model="code"
			:extensions="extensions"
			:tab-size="2"
			:autofocus="autofocus"
			:indent-with-tab="true"
			:style="{ height: height }"
			:disabled="readonly"
			@ready="setEditorValue"
			@blur="emitEditorValue"
		/>

		<Button v-if="showSaveButton" @click="emit('save', code)" class="mt-3 w-full text-base">Save</Button>
		<ErrorMessage class="text-xs leading-4" v-if="errorMessage" :message="errorMessage" />
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Codemirror } from "vue-codemirror"
import { json } from "@codemirror/lang-json"
import { javascript } from "@codemirror/lang-javascript"
import { python } from "@codemirror/lang-python"
import { html } from "@codemirror/lang-html"
import { css } from "@codemirror/lang-css"
import { autocompletion, closeBrackets, type CompletionContext } from "@codemirror/autocomplete"
import { syntaxTree } from "@codemirror/language"
import { EditorView } from "@codemirror/view"
import { tomorrow } from "thememirror"
import { jsToJson, jsonToJs } from "@/utils/helpers"

const props = withDefaults(
	defineProps<{
		language: "json" | "javascript" | "html" | "css" | "python"
		modelValue: string | object | Array<string | object> | null
		readonly?: boolean
		height?: string
		autofocus?: boolean
		showSaveButton?: boolean
		showLineNumbers?: boolean
		completions?: Function | null
	}>(),
	{
		language: "javascript",
		modelValue: null,
		height: "250px",
		showLineNumbers: true,
		completions: null,
	},
)
const emit = defineEmits(["update:modelValue", "save"])

const code = ref<string>("")
const setEditorValue = () => {
	let value = props.modelValue ?? ""
	try {
		if (props.language === "json" || typeof value === "object") {
			value = jsToJson(value)
		}
	} catch (e) {
		// do nothing
	}
	code.value = value
}

const errorMessage = ref("")
const emitEditorValue = () => {
	try {
		errorMessage.value = ""
		let value = code.value || ""
		if (
			value &&
			!value.startsWith("{{") &&
			(props.language === "json" || typeof props.modelValue === "object")
		) {
			value = jsonToJs(value)
		}

		if (!props.showSaveButton && !props.readonly) {
			emit("update:modelValue", value)
		}
	} catch (e) {
		console.error("Error while parsing JSON for editor", e)
		errorMessage.value = `Invalid object/JSON: ${e.message}`
	}
}

const extensions = [
	getLanguageExtension(),
	closeBrackets(),
	tomorrow,
	EditorView.lineWrapping,
	EditorView.theme({
		"&": {
			fontFamily: "monospace",
			fontSize: "12px",
		},
		".cm-gutters": {
			display: props.showLineNumbers ? "flex" : "none",
		},
	}),
]
const autocompletionOptions = {
	activateOnTyping: true,
	maxRenderedOptions: 10,
	closeOnBlur: false,
	icons: false,
	optionClass: () => "flex h-7 !px-2 items-center rounded !text-gray-600",
}
if (props.completions) {
	autocompletionOptions.override = [
		(context: CompletionContext) => {
			return props.completions?.(context, syntaxTree(context.state))
		},
	]
}
extensions.push(autocompletion(autocompletionOptions))

function getLanguageExtension() {
	switch (props.language) {
		case "json":
			return json()
		case "javascript":
			return javascript()
		case "html":
			return html()
		case "python":
			return python()
		case "css":
			return css()
	}
}
</script>
