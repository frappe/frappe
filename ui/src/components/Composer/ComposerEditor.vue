<template>
	<div class="flex h-full min-h-0 flex-col">
		<Editor
			ref="editorRef"
			v-model="body"
			:extensions="extensions"
			:placeholder="placeholder"
			:upload-function="uploadFunction"
		>
			<template #default>
				<div
					class="flex min-h-0 flex-1 flex-col"
					@keydown.ctrl.enter.capture.stop="submit"
					@keydown.meta.enter.capture.stop="submit"
					@keydown.esc.stop="onEscape"
					@keydown.ctrl.a.stop="selectAll"
					@keydown.meta.a.stop="selectAll"
					@keydown.delete="onDeleteAcrossQuote"
					@keydown.backspace="onDeleteAcrossQuote"
				>
					<slot name="top" />

					<EditorBubbleMenu :items="commentToolbar" />
					<EditorTableMenu />

					<div
						class="flex max-h-[50vh] min-h-0 flex-1 flex-col overflow-y-auto px-2.5 pb-2.5"
					>
						<EditorContent
							class="prose-sm max-w-full flex-1 pb-8 pt-4 [&_p.reply-to-content]:hidden"
						/>
						<!--
							Quoted reply lives outside the editor: tiptap parses HTML into its
							schema and drops what it can't represent, which mangles email tables
							and inline styling. A sibling contenteditable preserves the original;
							appended back on send.
						-->
						<details
							v-if="quotedContent"
							class="mb-2"
							:open="isQuoteExpanded"
							@toggle="onQuoteToggle"
						>
							<summary
								class="w-fit cursor-pointer select-none rounded px-1 text-sm font-bold leading-[1.15] text-ink-gray-5 bg-surface-gray-2 list-none [&::-webkit-details-marker]:hidden"
							>
								•••
							</summary>
							<div
								ref="quotedContentRef"
								contenteditable="true"
								class="prose mx-1 my-2 !max-w-full border-s-4 border-outline-gray-2 ps-4 text-sm focus:outline-none"
								@input="onQuotedInput"
							/>
						</details>
					</div>

					<div class="mt-auto">
						<div
							v-if="attachments.length"
							ref="attachmentRow"
							class="my-2 flex overflow-x-auto gap-2 px-2.5"
						>
							<Button
								v-for="attachment in attachments"
								:key="attachment.file_url"
								theme="gray"
								variant="subtle"
								:label="compactAttachments ? undefined : attachment.file_name"
								:title="attachment.file_name"
								:class="compactAttachments ? 'w-8 shrink-0' : 'min-w-0 max-w-36'"
							>
								<template #prefix>
									<LucideFileImage class="size-3.5 shrink-0" />
								</template>
								<template v-if="!compactAttachments" #suffix>
									<span
										class="lucide-x size-3.5 cursor-pointer shrink-0"
										@click.self.stop="removeAttachment(attachment)"
									/>
								</template>
							</Button>
						</div>

						<div class="flex items-center justify-between gap-2 px-2.5 pb-2.5">
							<div class="relative -ml-1.5 overflow-hidden" style="max-width: 70%">
								<!-- p-0.5 keeps button focus rings from being clipped by overflow-x-auto. -->
								<div
									ref="toolbarScroller"
									class="ml-1 flex items-center gap-1 overflow-x-auto p-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
								>
									<Button
										v-if="uploadFunction"
										variant="ghost"
										size="sm"
										:icon="LucidePaperclip"
										aria-label="Attach file"
										class="shrink-0"
										:disabled="isUploading"
										@click="attachInput?.click()"
									/>
									<input
										ref="attachInput"
										type="file"
										class="hidden"
										@change="onAttachPicked"
									/>
									<slot
										name="actions"
										v-bind="{ addAttachment, setUploading }"
									/>
									<!-- Same divider the menu uses between its own sections. -->
									<span
										v-if="uploadFunction || $slots.actions"
										class="mx-1 h-5 w-px shrink-0 bg-surface-gray-3"
										aria-hidden="true"
									/>
									<EditorFixedMenu :items="emailToolbar" button-size="sm" />
								</div>
								<div
									v-show="!toolbarArrived.left"
									class="pointer-events-none absolute inset-y-0 left-0 w-8"
									style="
										background: linear-gradient(
											to right,
											var(--surface-base, white),
											transparent
										);
									"
								/>
								<div
									v-show="!toolbarArrived.right"
									class="pointer-events-none absolute inset-y-0 right-0 w-8"
									style="
										background: linear-gradient(
											to left,
											var(--surface-base, white),
											transparent
										);
									"
								/>
							</div>
							<div class="flex shrink-0 items-center gap-2">
								<Button v-if="!isEmpty" label="Discard" @click="reset" />
								<Button
									variant="solid"
									:label="submitLabel"
									:disabled="isDisabled"
									@click="submit"
								/>
							</div>
						</div>
					</div>
				</div>
			</template>
		</Editor>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef, watch } from "vue";
import { useScroll } from "@vueuse/core";
import { Button, toast } from "frappe-ui";
import LucideFileImage from "~icons/lucide/file-image";
import LucidePaperclip from "~icons/lucide/paperclip";
import {
	Editor,
	EditorContent,
	EditorBubbleMenu,
	EditorFixedMenu,
	EditorTableMenu,
	RichTextKit,
	commentToolbar,
	Paragraph,
	H2,
	H3,
	H4,
	Separator,
	Bold,
	Italic,
	FontColor,
	AlignLeft,
	AlignCenter,
	AlignRight,
	BulletList,
	OrderedList,
	InsertImage,
	InsertVideo,
	InsertLink,
	Blockquote,
	InlineCode,
	HorizontalRule,
	InsertTable,
} from "frappe-ui/editor";
import { sanitizeHtml } from "../../utils/sanitize";
import type { ComposerEditorProps, CoreSubmitPayload, UploadedFile } from "./types";

const emailToolbar = [
	Paragraph,
	H2,
	H3,
	H4,
	Separator,
	Bold,
	Italic,
	FontColor,
	Separator,
	AlignLeft,
	AlignCenter,
	AlignRight,
	BulletList,
	OrderedList,
	Separator,
	InsertImage,
	InsertVideo,
	InsertLink,
	Blockquote,
	InlineCode,
	HorizontalRule,
	InsertTable,
];

const props = withDefaults(defineProps<ComposerEditorProps>(), {
	placeholder: "Type your message…",
	submitLabel: "Send",
});

const emit = defineEmits<{
	/** Only on explicit chip removal (so the host deletes server-side); not on reset/send. */
	"remove-attachment": [file: UploadedFile];
	/** Host runs the send and calls `reset()` itself when done. */
	submit: [payload: CoreSubmitPayload];
}>();

const editorRef = ref<InstanceType<typeof Editor> | null>(null);
const editor = computed(() => editorRef.value?.editor);

// Edge fades track scroll position so each side fades only while clipped.
const toolbarScroller = useTemplateRef<HTMLElement>("toolbarScroller");
const { arrivedState: toolbarArrived } = useScroll(toolbarScroller);

const mentionItems = computed(() =>
	(props.mentions ?? []).map((option) => ({
		id: option.value,
		label: option.label,
	}))
);

// Built once so the editor isn't torn down on change; reactive bits thread in via
// getters. Host extensions land after RichTextKit so they can override its defaults.
const extensions = [
	RichTextKit.configure({
		heading: { levels: [2, 3, 4, 5, 6] },
		mention: { items: () => mentionItems.value },
	}),
	...(props.extensions ?? []),
];

const body = defineModel<string>("body", { default: "" });

// Quoted reply, kept out of the editor body and appended back on send.
const quotedContent = defineModel<string | null>("quoted", { default: null });
const quotedContentRef = ref<HTMLElement | null>(null);
const isQuoteExpanded = ref(false);

// Keep the ref in step with native user toggles, or `:open` silently no-ops later.
function onQuoteToggle(event: Event) {
	isQuoteExpanded.value = (event.target as HTMLDetailsElement).open;
}

// Native Ctrl/Cmd+A only spans one contenteditable; stretch it across body + quote.
function selectAll(event: KeyboardEvent) {
	const editorDom = editor.value?.view?.dom as HTMLElement | undefined;
	const quotedEl = quotedContentRef.value;
	const selection = window.getSelection();
	const active = document.activeElement;
	if (!selection || !editorDom) return;
	if (!editorDom.contains(active) && !quotedEl?.contains(active)) return;

	// Reveal the quote only once we know the selection will span it.
	isQuoteExpanded.value = true;
	event.preventDefault();
	editor.value?.commands?.selectAll();
	selection.removeAllRanges();
	const range = document.createRange();
	if (quotedEl) {
		range.setStartBefore(editorDom);
		range.setEndAfter(quotedEl);
	} else {
		range.selectNodeContents(editorDom);
	}
	selection.addRange(range);
}

// After a select-all spanning both editables, delete clears both.
function onDeleteAcrossQuote(event: KeyboardEvent) {
	const selection = window.getSelection();
	const quotedEl = quotedContentRef.value;
	const editorDom = editor.value?.view?.dom as HTMLElement | undefined;
	if (!selection || selection.isCollapsed || !quotedEl || !editorDom) return;

	if (selection.containsNode(editorDom, true) && selection.containsNode(quotedEl, true)) {
		event.preventDefault();
		editor.value?.commands?.clearContent();
		body.value = "";
		quotedContent.value = null;
		selection.removeAllRanges();
	}
}

function onQuotedInput() {
	const html = quotedContentRef.value?.innerHTML ?? "";
	quotedContent.value = isContentEmpty(html) ? null : html;
}

// Paint the quoted block when the model changes from outside; user edits no-op.
watch(
	quotedContent,
	(next) => {
		if (!next) return;
		nextTick(() => {
			const el = quotedContentRef.value;
			if (el && el.innerHTML !== next) el.innerHTML = sanitizeHtml(next);
		});
	},
	{ immediate: true }
);

/** Body plus the quoted reply, appended as a blockquote at send time. */
function buildMessage() {
	const quoted = quotedContentRef.value?.innerHTML;
	return quoted
		? `${body.value}<p class="reply-to-content"></p><blockquote>${quoted}</blockquote>`
		: body.value;
}

const attachments = ref<UploadedFile[]>([]);
const isUploading = ref(false);
const attachmentRow = useTemplateRef<HTMLElement>("attachmentRow");
const compactAttachments = ref(false);

watch(attachmentRow, (el, _prev, onCleanup) => {
	if (!el) return;
	const observer = new ResizeObserver(() => {
		compactAttachments.value = el.scrollWidth > el.clientWidth;
	});
	observer.observe(el);
	onCleanup(() => observer.disconnect());
});

watch(attachments, () => {
	nextTick(() => {
		const el = attachmentRow.value;
		if (el) compactAttachments.value = el.scrollWidth > el.clientWidth;
	});
});

function addAttachment(file: UploadedFile) {
	attachments.value.push(file);
}

function setUploading(value: boolean) {
	isUploading.value = value;
}

const attachInput = useTemplateRef<HTMLInputElement>("attachInput");

// Bumped by reset() so a late-arriving upload can't re-add a discarded file.
let uploadEpoch = 0;

async function onAttachPicked(event: Event) {
	const input = event.target as HTMLInputElement;
	const file = input.files?.[0];
	// Reset so picking the same file again still fires `change`.
	input.value = "";
	if (!file || !props.uploadFunction) return;
	const epoch = uploadEpoch;
	isUploading.value = true;
	try {
		const uploaded = await props.uploadFunction(file);
		if (epoch !== uploadEpoch) return;
		addAttachment({
			name: uploaded.name ?? uploaded.file_url,
			file_name: uploaded.file_name,
			file_url: uploaded.file_url,
			file_type: uploaded.file_type ?? "",
			file_size: uploaded.file_size,
		});
	} catch {
		if (epoch === uploadEpoch) toast.error("Failed to upload the attachment.");
	} finally {
		if (epoch === uploadEpoch) isUploading.value = false;
	}
}

function removeAttachment(file: UploadedFile) {
	attachments.value = attachments.value.filter((a) => a !== file);
	emit("remove-attachment", file);
}

// Sendable = body or attachment (a quoted reply alone isn't); never mid-upload.
const isDisabled = computed(
	() => (isContentEmpty(body.value) && !attachments.value.length) || isUploading.value
);

const isEmpty = computed(
	() => isContentEmpty(body.value) && !attachments.value.length && !quotedContent.value
);

function isContentEmpty(content: string) {
	if (!content) return true;
	const doc = new DOMParser().parseFromString(content, "text/html");
	if (doc.querySelector("img, video, iframe, embed, object")) return false;
	return (doc.body.textContent ?? "").trim().length === 0;
}

function focus() {
	setTimeout(() => editor.value?.commands?.focus("start"), 0);
}

function submit() {
	if (isDisabled.value) return;
	emit("submit", { body: buildMessage(), attachments: attachments.value });
}

// An editor popup (mention list, etc.) that handled Esc marks it via preventDefault.
function onEscape(event: KeyboardEvent) {
	if (!event.defaultPrevented) reset();
}

function reset() {
	uploadEpoch++;
	isUploading.value = false;
	body.value = "";
	attachments.value = [];
	quotedContent.value = null;
	isQuoteExpanded.value = false;
	focus();
}

defineExpose({ editor, focus, reset, submit });
</script>
