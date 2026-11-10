<template>
	<Editor :model-value="content" format="markdown" :extensions="extensions" :editable="false">
		<EditorContent class="max-w-none" />
	</Editor>
</template>

<script setup lang="ts">
import { Editor, EditorContent, Markdown, RichTextKit } from "frappe-ui/editor";

defineProps<{ content: string }>();

const extensions = [RichTextKit, Markdown];
</script>
