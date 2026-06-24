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

		<TextEditor
			ref="editorRef"
			class="flex min-h-0 flex-1 flex-col"
			:editor-class="[
				'prose-sm max-w-full pb-8 pt-2 min-h-[6rem]',
				'[&_p.reply-to-content]:hidden',
			]"
			:content="body"
			:placeholder="placeholder"
			:starterkit-options="{ heading: { levels: [2, 3, 4, 5, 6] } }"
			:upload-function="uploadFunction"
			:mentions="mentions"
			@change="body = $event"
			@keydown.ctrl.enter.capture.stop="submit"
			@keydown.meta.enter.capture.stop="submit"
			@keydown.esc.capture.stop="discard"
		>
			<template v-if="$slots.top" #top>
				<slot name="top" />
			</template>

			<!-- The editor area takes the slack and scrolls, so #bottom stays
				 pinned to the container's bottom edge. -->
			<template #editor="{ editor: editorInstance }">
				<div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
					<TextEditorContent :editor="editorInstance" class="min-h-0 flex-1" />
					<!-- Collapsible quoted reply: the original message being
						 replied to, kept out of the editor body and appended
						 back on send. -->
					<details v-if="quotedContent" class="mb-2 mt-auto" :open="isQuoteExpanded">
						<summary
							class="w-fit cursor-pointer select-none rounded px-1 text-ink-gray-5 hover:bg-surface-gray-2"
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
			</template>

			<template #bottom>
				<!-- Attachments -->
				<div v-if="attachments.length" class="my-2 flex flex-wrap gap-2 px-5">
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

				<div class="flex items-center justify-between gap-2">
					<!-- Utilities scroll horizontally so Discard/Send stay visible
						 in a narrow window. Wrappers fill this (attach, etc). -->
					<div class="flex min-w-0 flex-1 items-center gap-4 overflow-x-auto">
						<slot name="utilities" v-bind="{ addAttachment, setUploading }" />
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
			</template>
		</TextEditor>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { Button, TextEditor, TextEditorContent } from "frappe-ui";
import type { ComposerProps, UploadedFile } from "./types";

const props = withDefaults(defineProps<ComposerProps>(), {
	storageKey: null,
	placeholder: "Type your message…",
	label: "Send",
});

const emit = defineEmits<{
	/** Fired when the user discards the draft. */
	discard: [];
	/** Fired after a successful submit (wrappers reset their own fields here). */
	submitted: [];
	/** Fired only when the user removes an attachment chip, so the host can
	 *  delete that file server-side. NOT fired on reset/discard/send-clear —
	 *  those files were either never sent or already belong to the sent email. */
	"remove-attachment": [file: UploadedFile];
}>();

const editorRef = ref<InstanceType<typeof TextEditor> | null>(null);
const editor = computed(() => editorRef.value?.editor);

// The editable body. Exposed as `v-model:body` so a host can seed initial
// content (drafts, signatures, a forwarded message) and observe edits live for
// things like server-side draft autosave. Unbound, it's just local state.
const body = defineModel<string>("body", { default: "" });

// The original message being replied to. Held outside the editor body in a
// collapsible block, then appended back on send so the quoted thread travels
// with the reply without cluttering the compose area. Persisted under the
// storageKey when one is given; otherwise it lives only in memory for the
// session.
const quotedStorageKey = props.storageKey ? `${props.storageKey}:quoted-reply` : null;
const quotedContent = ref<string | null>(
	quotedStorageKey ? localStorage.getItem(quotedStorageKey) : null
);
const quotedContentRef = ref<HTMLElement | null>(null);
const isQuoteExpanded = ref(false);

watch(quotedContent, (value) => {
	if (!quotedStorageKey) return;
	if (value) localStorage.setItem(quotedStorageKey, value);
	else localStorage.removeItem(quotedStorageKey);
});

function onQuotedInput() {
	quotedContent.value = quotedContentRef.value?.innerHTML || null;
}

watch(quotedContent, (next, prev) => {
	if (!prev && next) {
		nextTick(() => {
			if (quotedContentRef.value) quotedContentRef.value.innerHTML = next;
		});
	}
});

onMounted(() => {
	if (!quotedContent.value) return;
	nextTick(() => {
		if (quotedContentRef.value) {
			quotedContentRef.value.innerHTML = quotedContent.value as string;
		}
	});
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
// it through the `utilities` slot, and the files ride along in the payload. The
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

const loading = ref(false);
const isDisabled = computed(
	() => isContentEmpty(body.value) || loading.value || isUploading.value
);

/** True when the editor HTML carries no text and no media. */
function isContentEmpty(content: string) {
	if (!content) return true;
	const doc = new DOMParser().parseFromString(content, "text/html");
	if (doc.querySelector("img, video, iframe, embed, object")) return false;
	return (doc.body.textContent ?? "").trim().length === 0;
}

/** Plain text of an HTML fragment — used to compare signatures despite the
 *  editor's HTML normalization. */
function textOf(html?: string) {
	if (!html) return "";
	const doc = new DOMParser().parseFromString(html, "text/html");
	return (doc.body.textContent ?? "").trim();
}

/** The body with the signature placed a blank line below it. */
function withSignature(html?: string) {
	return html ? `<p><br></p>${html}` : "";
}

// The host owns the signature content and switches it when the sending identity
// changes; we own the placement. Seed it into an empty body, and swap it on
// change — but only while the user hasn't written over it (compared by text).
watch(
	() => props.signature,
	(next, previous) => {
		const untouched =
			isContentEmpty(body.value) || textOf(body.value) === textOf(withSignature(previous));
		if (untouched) body.value = withSignature(next);
	},
	{ immediate: true }
);

function focus() {
	setTimeout(() => editor.value?.commands?.focus("start"), 0);
}

// Hand the message to the wrapper's send method, and reset on success. The
// wrapper owns delivery (and any validation); the draft is kept if it throws.
async function submit() {
	if (isDisabled.value) return;

	loading.value = true;
	try {
		await props.onSubmit?.({
			body: buildMessage(),
			attachments: attachments.value,
		});
	} catch (error) {
		return;
	} finally {
		loading.value = false;
	}
	reset();
	emit("submitted");
}

function reset() {
	// Re-seed the signature so a fresh compose still shows it (empty otherwise).
	body.value = withSignature(props.signature);
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
