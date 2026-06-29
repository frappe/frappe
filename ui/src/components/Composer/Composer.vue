<template>
	<!--
		The shared editing core behind EmailComposer and CommentComposer. It owns
		the editor body, attachments, the Discard/Send toolbar, and the submit flow
		(loading → reset, keeping the draft if the handler throws).

		It is window-agnostic *content*: it fills its container and scrolls the
		editor internally so the toolbar stays pinned. Drop it inline, or into a
		FloatingWindow's default slot — the host owns the window chrome (drag,
		resize, dock/pop-out). Channel bits (header, recipient fields, toolbar
		extras) come in via slots.
	-->
	<div class="flex h-full min-h-0 flex-col">
		<!-- Channel header (e.g. "Via Email" + field toggles), above the editor. -->
		<slot name="header" />

		<!-- frappe-ui's molecule Editor is renderless: it owns the editor
			 lifecycle and v-model, and we render the layout (top fields, scrolling
			 body, bottom toolbar) inside its slot using EditorContent + the menus. -->
		<Editor
			ref="editorRef"
			v-model="body"
			:extensions="extensions"
			:placeholder="placeholder"
			:upload-function="uploadFn"
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

					<!-- Fixed editor space (helpdesk-style): a bounded height that
						 scrolls its own content, so the compose area stays the same
						 whether the window is docked or floating, and the toolbar
						 below it never moves. -->
					<div class="flex max-h-[50vh] min-h-[7rem] flex-col overflow-y-auto px-2.5">
						<EditorContent
							class="prose-sm max-w-full flex-1 pb-8 pt-2 [&_p.reply-to-content]:hidden"
						/>
						<!-- Collapsible quoted reply: the original message being
							 replied to, kept out of the editor body and appended
							 back on send. -->
						<details v-if="quotedContent" class="mb-2 mt-auto" :open="isQuoteExpanded">
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

					<!-- Attachments + actions, pinned to the bottom (mt-auto absorbs the
						 slack above) so the Discard/Send row sits at the foot of the
						 window when it's taller than the bounded editor. -->
					<div class="mt-auto">
						<!-- Attachments -->
						<div
							v-if="attachments.length"
							class="my-2 flex flex-wrap gap-2 px-5"
						>
							<Button
								v-for="attachment in attachments"
								:key="attachment.file_url"
								theme="gray"
								variant="subtle"
								:label="attachment.file_name"
							>
								<template #suffix>
									<span
										class="lucide-x size-3.5 cursor-pointer"
										@click.self.stop="removeAttachment(attachment)"
									/>
								</template>
							</Button>
						</div>

						<div class="flex items-center justify-between gap-2 px-2.5 pb-2.5">
							<!-- Host actions (attach, saved replies, …) scroll horizontally
								 so Discard/Send stay visible in a narrow window. -->
							<div
								class="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto"
							>
								<slot name="actions" v-bind="{ addAttachment, setUploading }" />
							</div>
							<div class="flex shrink-0 items-center gap-2">
								<Button label="Discard" @click="discard" />
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
import { computed, nextTick, ref, watch } from "vue";
import { Button } from "frappe-ui";
import {
	Editor,
	EditorContent,
	EditorBubbleMenu,
	CommentKit,
	commentToolbar,
	type UploadedFile as EditorUploadedFile,
} from "frappe-ui/editor";
import type { ComposerProps, CoreSubmitPayload, UploadedFile } from "./types";

const props = withDefaults(defineProps<ComposerProps>(), {
	placeholder: "Type your message…",
	label: "Send",
});

const emit = defineEmits<{
	/** The user submitted: the built message body + attachments. The host runs
	 *  the send (set `loading` while it does) and calls the exposed `reset()` on
	 *  success — the composer no longer awaits or resets itself. */
	submit: [payload: CoreSubmitPayload];
	/** Fired when the user discards the draft. */
	discard: [];
	/** Fired only when the user removes an attachment chip, so the host can
	 *  delete that file server-side. NOT fired on reset/discard/send-clear —
	 *  those files were either never sent or already belong to the sent email. */
	"remove-attachment": [file: UploadedFile];
}>();

const editorRef = ref<InstanceType<typeof Editor> | null>(null);
const editor = computed(() => editorRef.value?.editor);

// @-mention options, mapped from the host's { label, value } list to the
// editor's { id, label } shape. A getter keeps it live, so a late-loading list
// (e.g. agents fetched after mount) lights up without recreating the editor.
const mentionItems = computed(() =>
	(props.mentionOptions ?? []).map((option) => ({
		id: option.value,
		label: option.label,
	}))
);

// Comment-grade rich text (bold/italic/lists/links/images/mentions). Built once
// so the editor isn't torn down on every change; reactive bits (mentions,
// placeholder, upload) thread in through getters / Editor props.
const extensions = [
	CommentKit.configure({
		heading: { levels: [2, 3, 4, 5, 6] },
		mention: { items: () => mentionItems.value },
	}),
];

// The host's upload handler is typed loosely (Promise<unknown>); the editor
// wants the uploaded file's shape back. Same call, narrowed for the prop.
const uploadFn = computed(
	() => props.uploadFunction as ((file: File) => Promise<EditorUploadedFile>) | undefined
);

// The editable body. Exposed as `v-model:body` so a host can seed initial
// content (drafts, signatures, a forwarded message) and observe edits live for
// things like server-side draft autosave. Unbound, it's just local state.
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

// Attachment state lives here (the toolbar renders the chips); wrappers add to
// it through the `actions` slot, and the files ride along in the payload. The
// host learns about an explicit user removal via `remove-attachment` (to clean
// up server-side) — distinct from clearing the list on reset, which is silent.
const attachments = ref<UploadedFile[]>([]);
const isUploading = ref(false);

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

// Emit the built message for the host to deliver. We don't await or reset here:
// the host owns delivery (and `loading`), and calls the exposed `reset()` on
// success — so a failed send simply leaves the draft untouched.
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
