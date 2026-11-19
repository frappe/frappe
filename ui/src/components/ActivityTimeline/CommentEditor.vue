<template>
	<div @keydown.ctrl.enter="emit('save', content)" @keydown.meta.enter="emit('save', content)">
		<Editor
			ref="editorRef"
			v-model="content"
			:extensions="extensions"
			:upload-function="uploadFunction"
		>
			<EditorContent :class="editorClass" />
		</Editor>
	</div>
	<div class="mt-2 flex justify-end gap-2">
		<Button variant="outline" label="Discard" @click="emit('discard')" />
		<Button variant="solid" label="Save" @click="emit('save', content)" />
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { CommentKit, Editor, EditorContent } from "frappe-ui/editor";
import type { UploadedMedia } from "frappe-ui/editor";
import { nextTick, onMounted, ref } from "vue";

const props = defineProps<{
	content: string;
	editorClass?: string;
	uploadFunction?: (file: File) => Promise<UploadedMedia>;
}>();

const emit = defineEmits<{
	save: [content: string];
	discard: [];
}>();

const extensions = [CommentKit];
const editorRef = ref<InstanceType<typeof Editor> | null>(null);
const content = ref(props.content);

onMounted(() => nextTick(focusEditor));

function focusEditor() {
	const editor = editorRef.value?.editor;
	if (!editor) return;
	editor.commands.focus("end");
	editor.view.focus();
	setTimeout(() => {
		if (!editor.isFocused) editor.view.focus();
	}, 200);
}
</script>
