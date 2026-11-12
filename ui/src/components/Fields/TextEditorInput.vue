<template>
	<Editor
		:modelValue="buffer"
		:extensions="extensions"
		:placeholder="field.placeholder"
		:upload-function="upload"
		@update:modelValue="onInput"
	>
		<!-- A panel row has no frame or fixed toolbar: the box around it is the row's, and the
		     formatting bar floats below a selection. -->
		<div
			v-if="panel"
			class="text-editor-panel"
			data-slot="text-editor"
			@focusin="onFocusIn"
			@focusout="onFocusOut"
		>
			<!-- Fixed, or the scrolling body clips a bar below a selection on its last line. -->
			<EditorBubbleMenu
				:items="richTextBubble"
				:options="{ side: 'bottom', strategy: 'fixed' }"
			/>
			<EditorTableMenu />
			<div class="text-editor-body overflow-y-auto">
				<EditorContent
					class="min-h-7 max-w-full px-2 py-1 text-base leading-5"
					role="textbox"
					aria-multiline="true"
					:aria-label="field.placeholder"
					:aria-describedby="describedBy"
					:aria-invalid="invalid || undefined"
					:aria-required="field.reqd || undefined"
				/>
			</div>
		</div>
		<div
			v-else
			class="text-editor-frame flex flex-col rounded-4 border border-[--surface-gray-2] bg-surface-gray-2 transition-colors focus-within:border-outline-gray-4 focus-within:bg-surface-base focus-within:shadow-sm"
			data-slot="text-editor"
			@focusin="onFocusIn"
			@focusout="onFocusOut"
		>
			<div
				class="text-editor-toolbar flex items-center overflow-x-auto border-b border-outline-gray-1 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
			>
				<EditorFixedMenu :key="toolbarKey" :items="richTextToolbar" size="sm" />
			</div>
			<EditorTableMenu />
			<div class="text-editor-body overflow-y-auto">
				<EditorContent
					class="prose-sm min-h-32 max-w-full px-3 py-2"
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
import { computed, ref, watch } from "vue";
import { Extension } from "@tiptap/core";
import {
	Editor,
	EditorBubbleMenu,
	EditorContent,
	EditorFixedMenu,
	EditorTableMenu,
} from "frappe-ui/editor";
import type { MediaUploadRequestOptions } from "frappe-ui/editor";
import { isEmptyHtml } from "../RichText/html";
import { richTextBubble, richTextKit, richTextToolbar, useToolbarKey } from "../RichText/kit";
import { uploadMedia } from "../RichText/upload";
import type { FieldMeta } from "./types";

const props = defineProps<{
	field: FieldMeta;
	modelValue: string | null | undefined;
	labelId?: string;
	describedBy?: string;
	invalid?: boolean;
	/** Drawn in a panel row: no frame or fixed toolbar, six lines tall at most. */
	panel?: boolean;
}>();
const emit = defineEmits<{
	"update:modelValue": [value: string];
	change: [value: string];
}>();

const { key: toolbarKey, extension: toolbarKeyExtension } = useToolbarKey();

// ProseMirror marks every Esc handled, so a dialog around the field never sees it. Esc leaves
// the body instead, after any open menu takes it; the next Esc reaches the dialog.
const extensions = [
	richTextKit(),
	toolbarKeyExtension,
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

function onFocusIn() {
	atFocus ??= value.value;
}

// The link editor and the table menus are portalled out of the field.
const OWN_POPUPS = '.editor-popover,[data-slot="table-menu"],[role="menu"]';

// Focus moving within the field, as onto its toolbar or one of its popups, keeps the edit open.
function onFocusOut(event: FocusEvent) {
	const field = event.currentTarget as HTMLElement;
	const next = event.relatedTarget as HTMLElement | null;
	if (field.contains(next) || next?.closest(OWN_POPUPS)) return;
	if (atFocus !== null && value.value !== atFocus) emit("change", value.value);
	atFocus = null;
}

// A detached file: the record's save adopts it and applies `make_attachments_public`.
// Never `attached_to_field`: the File would then overwrite this field's HTML with its URL.
function upload(file: File, options?: MediaUploadRequestOptions) {
	return uploadMedia(file, options);
}

const maxHeight = computed(() => {
	if (props.panel) return "8rem";
	const height = props.field.maxHeight?.trim();
	if (!height) return "50vh";
	return /^\d+(\.\d+)?$/.test(height) ? `${height}px` : height;
});
</script>

<style scoped>
.text-editor-body {
	max-height: v-bind(maxHeight);
}

/* A panel row's lines are the textarea's: 20 high, no block margins, so rest and edit match. */
.text-editor-panel :deep(.ProseMirror) {
	outline: none;
	overflow-wrap: anywhere;
}
.text-editor-panel :deep(.ProseMirror > *),
.text-editor-panel :deep(.ProseMirror li > p) {
	margin: 0;
}
.text-editor-panel :deep(.ProseMirror :is(h1, h2, h3, h4, h5, h6)) {
	font-size: inherit;
	line-height: inherit;
	font-weight: 600;
}
.text-editor-panel :deep(.ProseMirror :is(ul, ol)) {
	margin: 0;
	padding-inline-start: 1.25rem;
}

/* Like frappe-ui's subtle inputs. A plain `hover:` fill would outrank `focus-within:` while typing. */
.text-editor-frame:not(:focus-within):hover {
	border-color: var(--outline-elevation-2);
	background-color: var(--surface-gray-3);
}

/* At rest the gray fill would swallow the toolbar's gray-3 pressed and hover fills and its lines. */
.text-editor-frame:not(:focus-within) .text-editor-toolbar :deep([aria-pressed="true"]) {
	background-color: transparent;
}
.text-editor-frame:not(:focus-within) .text-editor-toolbar :deep(button:not(:disabled):hover),
.text-editor-frame:not(:focus-within) :deep([data-slot="menu-separator"]) {
	background-color: var(--surface-gray-4);
}
.text-editor-frame:not(:focus-within) .text-editor-toolbar {
	border-color: var(--outline-gray-2);
}
</style>
