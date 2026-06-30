<template>
	<!-- Shared editing core for EmailComposer and CommentComposer: editor body,
		 attachments, Discard/Send toolbar. Window-agnostic content — the host owns
		 the window chrome; channel bits arrive via slots. -->
	<div class="flex h-full min-h-0 flex-col">
		<slot name="header" />

		<!-- frappe-ui's Editor is renderless: we render the layout in its slot. -->
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
					@keydown.esc.capture.stop="discard"
					@keydown.ctrl.a.stop="selectAll"
					@keydown.meta.a.stop="selectAll"
					@keydown.delete="onDeleteAcrossQuote"
					@keydown.backspace="onDeleteAcrossQuote"
				>
					<slot name="top" />

					<!-- Selection formatting popup. -->
					<EditorBubbleMenu :items="commentToolbar" />
					<!-- Contextual table controls (shown while cursor is inside a table). -->
					<EditorTableMenu />

					<!-- Editor space: min 7rem, grows to a 50vh cap then scrolls; toolbar stays pinned. -->

					<div
						class="flex max-h-[50vh] min-h-[7rem] flex-1 flex-col overflow-y-auto px-2.5 pb-2.5"
					>
						<EditorContent
							class="prose-sm max-w-full flex-1 pb-8 pt-2 [&_p.reply-to-content]:hidden"
						/>
						<!-- Collapsible quoted reply: the original message being
							 replied to, kept out of the editor body and appended
							 back on send. -->
						<details v-if="quotedContent" class="mb-2" :open="isQuoteExpanded">
							<summary
								class="w-fit cursor-pointer select-none rounded px-1 text-sm leading-none text-ink-gray-5 bg-surface-gray-2 list-none [&::-webkit-details-marker]:hidden"
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
						<!-- Attachments -->
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
							<!-- Host actions: clipped to 50% width, scrollable, with a right-side
								 fade to signal overflow. -->
							<div class="relative overflow-hidden" style="max-width: 70%">
								<div class="flex items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
									<slot name="actions" v-bind="{ addAttachment, setUploading }" />
									<EditorFixedMenu :items="emailToolbar" button-size="sm" />
								</div>
								<!-- Fade indicating more content to the right -->
								<div
									class="pointer-events-none absolute inset-y-0 right-0 w-8"
									style="background: linear-gradient(to left, var(--surface-white, white), transparent)"
								/>
							</div>
							<div class="flex shrink-0 items-center gap-2">
								<Button label="Discard" :disabled="isEmpty" @click="discard" />
								<Button
									variant="solid"
									:label="label"
									:disabled="isDisabled"
									:loading="loading"
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
import { Button } from "frappe-ui";
import LucideFileImage from "~icons/lucide/file-image";
import {
	Editor,
	EditorContent,
	EditorBubbleMenu,
	EditorFixedMenu,
	EditorTableMenu,
	RichTextKit,
	commentToolbar,
	Paragraph, H2, H3, H4,
	Separator,
	Bold, Italic, FontColor,
	AlignLeft, AlignCenter, AlignRight,
	BulletList, OrderedList,
	InsertImage, InsertVideo, InsertLink,
	Blockquote, InlineCode, HorizontalRule,
	InsertTable,
} from "frappe-ui/editor";

const emailToolbar = [
	Paragraph, H2, H3, H4,
	Separator,
	Bold, Italic, FontColor,
	Separator,
	AlignLeft, AlignCenter, AlignRight,
	BulletList, OrderedList,
	Separator,
	InsertImage, InsertVideo, InsertLink,
	Blockquote, InlineCode, HorizontalRule, InsertTable,
];
import type { ComposerProps, CoreSubmitPayload, UploadedFile } from "./types";

const props = withDefaults(defineProps<ComposerProps>(), {
	placeholder: "Type your message…",
	label: "Send",
});

const emit = defineEmits<{
	/** Built body + attachments. Host runs the send and calls `reset()` on success. */
	submit: [payload: CoreSubmitPayload];
	discard: [];
	/** Only on explicit chip removal (so the host deletes server-side); not on reset/send. */
	"remove-attachment": [file: UploadedFile];
}>();

const editorRef = ref<InstanceType<typeof Editor> | null>(null);
const editor = computed(() => editorRef.value?.editor);

// @-mention options mapped to the editor's { id, label } shape. Kept live via a
// getter so a late-loading list works without recreating the editor.
const mentionItems = computed(() =>
	(props.mentionOptions ?? []).map((option) => ({
		id: option.value,
		label: option.label,
	}))
);

// Built once so the editor isn't torn down on change; reactive bits thread in via getters.
const extensions = [
	RichTextKit.configure({
		heading: { levels: [2, 3, 4, 5, 6] },
		mention: { items: () => mentionItems.value },
	}),
];

// Editable body, exposed as `v-model:body` so a host can seed and observe it.
const body = defineModel<string>("body", { default: "" });

// The original message being replied to. Held outside the editor body in a
// collapsible block, then appended back on send so the quoted thread travels
// with the reply without cluttering the compose area. In-memory for the session.
const quotedContent = ref<string | null>(null);
const quotedContentRef = ref<HTMLElement | null>(null);
const isQuoteExpanded = ref(false);

// Body and quoted reply are two separate contenteditables, so a native
// Ctrl/Cmd+A only spans the focused one. Select all of the editor's own
// content (so its internal state knows it's selected), then stretch the DOM
// selection from before the editor to after the quoted block.
function selectAll(event: KeyboardEvent) {
	isQuoteExpanded.value = true;
	const editorDom = editor.value?.view?.dom as HTMLElement | undefined;
	const quotedEl = quotedContentRef.value;
	const selection = window.getSelection();
	const active = document.activeElement;
	if (!selection || !editorDom) return;
	if (!editorDom.contains(active) && !quotedEl?.contains(active)) return;

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

// Backspace/Delete only empties the focused editable. When the selection spans
// both the editor body and the quoted block (i.e. after select-all), clear
// both so the whole composer empties.
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
	// Empty-of-text (stray <br>/<p></p> left after deleting) collapses to null,
	// so the quoted-reply block disappears instead of lingering empty.
	quotedContent.value = isContentEmpty(html) ? null : html;
}

watch(quotedContent, (next, prev) => {
	if (!prev && next) {
		nextTick(() => {
			if (quotedContentRef.value) quotedContentRef.value.innerHTML = next;
		});
	}
});

/** Body plus the quoted reply, appended as a blockquote at send time. */
function buildMessage() {
	const quoted = quotedContentRef.value?.innerHTML;
	return quoted
		? `${body.value}<p class="reply-to-content"></p><blockquote>${quoted}</blockquote>`
		: body.value;
}

/** Drop a quoted message into the collapsible block (clears the editable body). */
function setQuotedReply(content: string) {
	body.value = "";
	if (content !== quotedContent.value) {
		// Toggle through null so the watch re-populates the quoted block element.
		quotedContent.value = null;
		isQuoteExpanded.value = false;
		nextTick(() => (quotedContent.value = content));
	}
}

// Attachment state. Hosts add via the `actions` slot; explicit removals emit
// `remove-attachment` (reset clears silently).
const attachments = ref<UploadedFile[]>([]);
const isUploading = ref(false);
const attachmentRow = useTemplateRef<HTMLElement>("attachmentRow");
const compactAttachments = ref(false);

watch(attachmentRow, (el) => {
	if (!el) return;
	const check = () => { compactAttachments.value = el.scrollWidth > el.clientWidth; };
	const observer = new ResizeObserver(check);
	observer.observe(el);
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

function removeAttachment(file: UploadedFile) {
	attachments.value = attachments.value.filter((a) => a !== file);
	emit("remove-attachment", file);
}

const isDisabled = computed(
	() => isContentEmpty(body.value) || props.loading || isUploading.value
);

// Nothing to discard: empty body, no attachments, no quoted reply.
const isEmpty = computed(
	() => isContentEmpty(body.value) && !attachments.value.length && !quotedContent.value
);

/** True when the editor HTML carries no text and no media. */
function isContentEmpty(content: string) {
	if (!content) return true;
	const doc = new DOMParser().parseFromString(content, "text/html");
	if (doc.querySelector("img, video, iframe, embed, object")) return false;
	return (doc.body.textContent ?? "").trim().length === 0;
}

function focus() {
	setTimeout(() => editor.value?.commands?.focus("start"), 0);
}

// Emit for the host to deliver; it owns `loading` and calls `reset()` on success,
// so a failed send leaves the draft intact.
function submit() {
	if (isDisabled.value) return;
	emit("submit", { body: buildMessage(), attachments: attachments.value });
}

function reset() {
	// Clear the editor; the host re-seeds any default body (e.g. a signature).
	body.value = "";
	attachments.value = [];
	quotedContent.value = null;
	isQuoteExpanded.value = false;
	focus();
}

function discard() {
	reset();
	emit("discard");
}

defineExpose({ editor, focus, reset, submit, setQuotedReply, addAttachment });
</script>
