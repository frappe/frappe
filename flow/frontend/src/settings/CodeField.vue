<template>
	<CodeEditor v-model="model" :extensions="extensions" :editable="!disabled">
		<CodeEditorContent style="--code-max-height: 24rem; --code-min-height: 4.5rem" />
	</CodeEditor>
</template>

<script setup>
import { computed } from "vue";
import { CodeEditor, CodeEditorContent, CodeKit } from "frappe-ui/code-editor";
import { json, jsonParseLinter } from "@codemirror/lang-json";
import { python } from "@codemirror/lang-python";
import { linter, lintGutter } from "@codemirror/lint";

const props = defineProps({
	language: { type: String, default: "" },
	placeholder: { type: String, default: "" },
	disabled: { type: Boolean, default: false },
});
const model = defineModel({ type: String, default: "" });

// jinja stays plain text
const languages = {
	json: () => [json(), lintGutter(), linter(jsonParseLinter())],
	python: () => [python()],
};
const extensions = computed(() => [
	CodeKit.configure({ lineNumbers: {}, placeholder: props.placeholder || false }),
	...(languages[props.language]?.() ?? []),
]);
</script>
