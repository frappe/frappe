<template>
	<div class="flex flex-col">
		<codemirror
			v-model="model"
			:extensions="extensions"
			:tab-size="2"
			:autofocus="autofocus"
			:indent-with-tab="true"
			:style="{ height: height }"
			:disabled="readonly"
		/>

		<Button v-if="showSaveButton" @click="emit('save', model)" class="mt-3 w-full text-base">
			Save
		</Button>
	</div>
</template>

<script setup lang="ts">
import { Codemirror } from "vue-codemirror"
import { json } from "@codemirror/lang-json"
import { javascript } from "@codemirror/lang-javascript"
import { python } from "@codemirror/lang-python"
import { html } from "@codemirror/lang-html"
import { css } from "@codemirror/lang-css"
import { closeBrackets } from "@codemirror/autocomplete"
import { EditorView } from "@codemirror/view"
import { tomorrow } from "thememirror"

const props = withDefaults(
	defineProps<{
		language: "json" | "javascript" | "html" | "css" | "python"
		readonly?: boolean
		height?: string
		autofocus?: boolean
		showSaveButton?: boolean
		showLineNumbers?: boolean
	}>(),
	{
		language: "javascript",
		height: "250px",
		showLineNumbers: true,
	},
)
const model = defineModel<string>()
const emit = defineEmits(["save"])

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
		}
	})
]

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
