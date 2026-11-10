<template>
	<CodeEditor ref="editor" v-model="model" :extensions="extensions" :editable="!disabled">
		<CodeEditorContent style="--code-max-height: 24rem; --code-min-height: 4.5rem" />
	</CodeEditor>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
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

// frappe-ui makes the view detached, so CodeMirror puts its base styles in the document; in
// Flow's island the editor lives in a shadow root, which needs them in its own
const editor = ref(null);
onMounted(() => {
	const view = editor.value?.editor;
	const root = view?.dom.getRootNode();
	// a shadow root is a document fragment; a detached view's root is its own element
	if (root?.nodeType === Node.DOCUMENT_FRAGMENT_NODE) view.setRoot(root);
});

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
