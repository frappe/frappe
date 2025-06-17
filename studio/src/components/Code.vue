<template>
	<div class="flex h-full w-full flex-col gap-1.5">
		<InputLabel :class="[required ? `after:text-red-600 after:content-['_*']` : '']">
			{{ label }}
		</InputLabel>
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

		<Button v-if="showSaveButton" @click="emit('save', code)" class="mt-3 w-full text-base">Save</Button>
		<ErrorMessage class="text-xs leading-4" v-if="errorMessage" :message="errorMessage" />
	</div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch } from "vue"
import { Codemirror } from "vue-codemirror"
import { autocompletion, closeBrackets } from "@codemirror/autocomplete"
import { LanguageSupport } from "@codemirror/language"
import { EditorView } from "@codemirror/view"
import { tomorrow } from "thememirror"
import { jsToJson, jsonToJs } from "@/utils/helpers"

import InputLabel from "@/components/InputLabel.vue"

const props = withDefaults(
	defineProps<{
		language: "json" | "javascript" | "html" | "css" | "python"
		modelValue: string | object | Array<string | object> | null
		height?: string
		maxHeight?: string
		autofocus?: boolean
		showSaveButton?: boolean
		showLineNumbers?: boolean
		completions?: Function | null
		label?: string
		required?: boolean
		readonly?: boolean
	}>(),
	{
		language: "javascript",
		modelValue: null,
		height: "auto",
		maxHeight: "250px",
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
		console.log("Error while converting value to JSON", e)
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
const autocompleteExtension = ref()

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

	if (props.completions) {
		const languageData = (module as any)[`${props.language}Language`]
		autocompleteExtension.value = languageData.data.of({
			autocomplete: props.completions,
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

const extensions = computed(() => {
	const baseExtensions = [
		closeBrackets(),
		tomorrow,
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
	if (autocompleteExtension.value) {
		baseExtensions.push(autocompleteExtension.value)
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
</script>
