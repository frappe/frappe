<template>
	<Editor
		:modelValue="buffer"
		:extensions="extensions"
		:placeholder="field.placeholder"
		:upload-function="upload"
		@update:modelValue="onInput"
		@focus="onFocus"
		@blur="onBlur"
	>
		<div
			ref="root"
			class="flex flex-col rounded-4 border border-outline-gray-2 bg-surface-base hover:border-outline-gray-3 focus-within:border-outline-gray-4 focus-within:shadow-sm"
			data-slot="text-editor"
		>
			<div
				class="flex items-center overflow-x-auto border-b border-outline-gray-1 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
			>
				<EditorFixedMenu :items="richTextToolbar" size="sm" />
			</div>
			<EditorTableMenu />
			<div class="text-editor-body min-h-32 overflow-y-auto px-3">
				<EditorContent
					class="prose-sm max-w-full py-2"
					role="textbox"
					aria-multiline="true"
					:aria-labelledby="labelId"
					:aria-describedby="describedBy"
					:aria-invalid="invalid || undefined"
					:aria-required="field.reqd || undefined"
				/>
			</div>
		</div>
	</Editor>
</template>

<script setup lang="ts">
import { computed, inject, ref, useTemplateRef, watch } from "vue";
import { Extension } from "@tiptap/core";
import { Editor, EditorContent, EditorFixedMenu, EditorTableMenu } from "frappe-ui/editor";
import type { MediaUploadRequestOptions } from "frappe-ui/editor";
import { isEmptyHtml } from "../RichText/html";
import { richTextKit, richTextToolbar } from "../RichText/kit";
import { uploadMedia } from "../RichText/upload";
import { DocKey, ParentDocKey } from "./types";
import type { FieldMeta } from "./types";

const props = defineProps<{
	field: FieldMeta;
	modelValue: string | null | undefined;
	labelId?: string;
	describedBy?: string;
	invalid?: boolean;
}>();
const emit = defineEmits<{
	"update:modelValue": [value: string];
	change: [value: string];
}>();

const root = useTemplateRef<HTMLElement>("root");

// ProseMirror marks every Esc handled, so a dialog around the field never sees it. Esc leaves
// the body instead, after any open menu takes it; the next Esc reaches the dialog.
const extensions = [
	richTextKit(),
	Extension.create({
		name: "textEditorEscape",
		priority: 1,
		addKeyboardShortcuts() {
			return { Escape: () => this.editor.commands.blur() };
		},
	}),
];

// The editor's own HTML; an emptied editor keeps its empty block but stores "". A stored value
// reaches the doc only through an edit, so loading one never writes back.
const buffer = ref(props.modelValue ?? "");
const value = computed(() => (isEmptyHtml(buffer.value) ? "" : buffer.value));

// The value when focus arrived, or `null` with no focus. An edit made then, such as a finished
// upload, commits at once.
let atFocus: string | null = null;

watch(
	() => props.modelValue ?? "",
	(next) => {
		if (next === value.value) return;
		buffer.value = next;
		if (atFocus !== null) atFocus = next;
	}
);

function onInput(html: string | null) {
	const previous = value.value;
	buffer.value = html ?? "";
	if (value.value === previous) return;
	emit("update:modelValue", value.value);
	if (atFocus === null) emit("change", value.value);
}

function onFocus() {
	atFocus ??= value.value;
}

// A click on the field's own toolbar keeps the edit open.
function onBlur(event: FocusEvent) {
	if (root.value?.contains(event.relatedTarget as Node | null)) return;
	if (atFocus !== null && value.value !== atFocus) emit("change", value.value);
	atFocus = null;
}

const doc = inject(DocKey, null);
const parentDoc = inject(ParentDocKey, null);

// A saved record takes the file as an attachment; a new one, a detached file it adopts on save.
// Never `attached_to_field`: the File would then overwrite this field's HTML with its URL.
function upload(file: File, options?: MediaUploadRequestOptions) {
	const record = (parentDoc ?? doc)?.value;
	const attachTo =
		record?.doctype && record.name
			? { doctype: record.doctype, docname: record.name }
			: undefined;
	return uploadMedia(file, options, { isPrivate: true, attachTo });
}

const maxHeight = computed(() => {
	const height = props.field.maxHeight?.trim();
	if (!height) return "50vh";
	return /^\d+(\.\d+)?$/.test(height) ? `${height}px` : height;
});
</script>

<style scoped>
.text-editor-body {
	max-height: v-bind(maxHeight);
}
</style>
