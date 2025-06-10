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
import { onMounted, ref, computed, watch } from "vue"
import { Codemirror } from "vue-codemirror"
import { autocompletion, closeBrackets, type CompletionContext } from "@codemirror/autocomplete"
import { LanguageSupport, syntaxTree } from "@codemirror/language"
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

const languageExtension = ref<LanguageSupport>()

async function setLanguageExtension() {
	if (props.language === "json") {
		languageExtension.value = (await import("@codemirror/lang-json")).json()
	} else if (props.language === "javascript") {
		languageExtension.value = (await import("@codemirror/lang-javascript")).javascript()
	} else if (props.language === "html") {
		languageExtension.value = (await import("@codemirror/lang-html")).html()
	} else if (props.language === "css") {
		languageExtension.value = (await import("@codemirror/lang-css")).css()
	} else if (props.language === "python") {
		languageExtension.value = (await import("@codemirror/lang-python")).python()
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

const extensions = computed(() => {
	const baseExtensions = [
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
	if (languageExtension.value) {
		baseExtensions.push(languageExtension.value)
	}
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
	baseExtensions.push(autocompletion(autocompletionOptions))
	return baseExtensions
})
</script>
