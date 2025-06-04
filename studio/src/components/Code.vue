<template>
	<codemirror
		v-model="model"
		:extensions="extensions"
		:tab-size="2"
		:autofocus="autofocus"
		:indent-with-tab="true"
		:style="{ height: height }"
	/>
</template>

<script setup lang="ts">
import { Codemirror } from "vue-codemirror"
import { json } from "@codemirror/lang-json"
import { javascript } from "@codemirror/lang-javascript"
import { python } from "@codemirror/lang-python"
import { html } from "@codemirror/lang-html"
import { css } from "@codemirror/lang-css"
import { closeBrackets } from "@codemirror/autocomplete"

const props = withDefaults(
	defineProps<{
		language: "json" | "javascript" | "html" | "css" | "python"
		readonly?: boolean
		height?: string
		autofocus?: boolean
	}>(),
	{
		language: "javascript",
		height: "250px",
	},
)
const model = defineModel<string>()

const extensions = [getLanguageExtension(), closeBrackets()]

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
