<!-- Stand-in for @framework/ui's CodeEditorField until frappe/frappe#42965 lands; see vite/frameworkUICodeEditorShim.js -->
<template>
	<div class="space-y-1.5">
		<InputLabel v-if="field.label" :label="field.label" :required="field.reqd" />
		<CodeEditor
			:modelValue="modelValue ?? ''"
			:extensions="extensions"
			:editable="!field.readOnly"
			@update:modelValue="(value: string) => emit('update:modelValue', value)"
			@change="(value: string) => emit('change', value)"
		>
			<CodeEditorContent class="max-h-54" />
		</CodeEditor>
		<InputDescription v-if="field.description" :description="field.description" />
	</div>
</template>

<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import type { Extension } from "@codemirror/state"
import { InputDescription, InputLabel } from "frappe-ui/experimental"
import { CodeEditor, CodeEditorContent, CodeKit, loadLanguage } from "frappe-ui/code-editor"
import { fieldtypeToLanguage } from "@framework/ui/fields/fieldtypeToLanguage"

const props = defineProps<{ field: Record<string, any>; modelValue: any }>()
const emit = defineEmits<{ "update:modelValue": [value: string]; change: [value: string] }>()

const kit = props.field.placeholder ? CodeKit.configure({ placeholder: props.field.placeholder }) : CodeKit
const language = shallowRef<Extension | null>(null)

watch(
	() => fieldtypeToLanguage(props.field as any),
	(key) => {
		language.value = null
		loadLanguage(key as any)
			.then((extension) => (language.value = extension))
			.catch(() => {})
	},
	{ immediate: true },
)

const extensions = computed(() => [kit, language.value].filter(Boolean) as Extension[])
</script>
