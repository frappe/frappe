<template>
	<!--
		An email composer that owns its window: it wraps itself in a FloatingWindow
		so the title, field toggles, and float/dock control share one bar that
		doubles as the title bar / drag handle. `v-model:mode` drives docked /
		floating / minimized. Pass more than one `channel` (e.g. ["email", "comment"])
		to turn the title into a switcher and gain a `submit-comment` event.
	-->
	<!-- `:style` falls through onto FloatingWindow's panel (it forwards $attrs).
		 While docked we use it to pin a draggable height; floating/minimized keep
		 the window's own sizing (dockedStyle is undefined then). -->
	<FloatingWindow v-model:mode="windowMode" :minimizable="true" :style="dockedStyle">
		<template #header="{ mode, float, dock, minimize, expandFromTray }">
			<!-- Docked-only top grip: drag up to grow the compose area (the host
				 container pins the bottom). Anchors to the panel, which is relative. -->
			<button
				v-if="mode === 'docked'"
				type="button"
				aria-label="Resize comment box"
				class="absolute left-1/2 top-0 z-10 flex h-6 w-24 -translate-x-1/2 cursor-ns-resize touch-none items-center justify-center rounded-full opacity-60 transition-opacity hover:opacity-100 focus:opacity-100"
				@pointerdown.prevent="startDockedResize"
			>
				<span class="h-1 w-10 rounded-full bg-surface-gray-4" />
			</button>
			<ComposerHeader
				class="px-2.5"
				:title="channelLabel"
				:expandable="expandable"
				:floating="mode !== 'docked'"
				:minimizable="true"
				:minimized="mode === 'minimized'"
				@expand="mode === 'docked' ? float() : dock()"
				@minimize="mode === 'minimized' ? expandFromTray() : minimize()"
			>
				<!-- Multi-channel: the title becomes an Email/Comment pill toggle. -->
				<template v-if="channels.length > 1" #title>
					<TabButtons v-model="channel" :options="channelOptions" />
				</template>

				<!-- Reveal the optional Cc/Bcc recipient rows. Email-only, and hidden
					 while minimized (the tray strip shows just the label). -->
				<template v-if="channel === 'email' && mode !== 'minimized'" #actions>
					<Button
						v-if="fields?.includes('cc')"
						variant="ghost"
						label="CC"
						:class="showCc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
						@click="showCc = !showCc"
					/>
					<Button
						v-if="fields?.includes('bcc')"
						variant="ghost"
						label="BCC"
						:class="showBcc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
						@click="showBcc = !showBcc"
					/>
				</template>
			</ComposerHeader>
		</template>

		<Composer
			ref="composer"
			class="min-h-0 flex-1"
			:placeholder="placeholder"
			:label="submitLabel"
			:loading="loading"
			:upload-function="uploadFunction"
			:mention-options="mentionOptions"
			v-model:body="body"
			@submit="handleSubmit"
			@discard="emit('discard')"
			@remove-attachment="emit('remove-attachment', $event)"
		>
			<!-- Email-only: the host's From picker and the recipient rows. Comment
				 mode is just the editing core, so they're hidden. -->
			<template #top>
				<template v-if="channel === 'email'">
					<slot name="from" />
					<RecipientFields
						v-model="recipients"
						v-model:subject="subject"
						:show-subject="showSubject"
						:show-cc="showCc"
						:show-bcc="showBcc"
						:search="searchRecipients"
					/>
				</template>
			</template>

			<!-- Attachments, canned-response pickers, etc. are host-supplied: wire a
				 FileUploader to `addAttachment` and report progress via `setUploading`. -->
			<template v-if="$slots.actions" #actions="actionProps">
				<slot name="actions" v-bind="actionProps" />
			</template>
		</Composer>
	</FloatingWindow>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Button, TabButtons, toast } from "frappe-ui";
import { FloatingWindow, type WindowMode } from "frappe-ui/experimental";
import Composer from "../Composer.vue";
import ComposerHeader from "../ComposerHeader.vue";
import RecipientFields from "./RecipientFields.vue";
import type {
	Channel,
	CommentPayload,
	CoreSubmitPayload,
	EmailComposerProps,
	EmailPayload,
	Recipients,
	UploadedFile,
} from "../types";

const props = withDefaults(defineProps<EmailComposerProps>(), {
	fields: () => ["cc", "bcc"],
	expandable: true,
	channels: () => ["email"],
});

const emit = defineEmits<{
	/** Email channel: the user sent the email (full envelope). */
	submit: [payload: EmailPayload];
	/** Comment channel: the user posted an internal comment (body + attachments). */
	"submit-comment": [payload: CommentPayload];
	discard: [];
	"remove-attachment": [file: UploadedFile];
}>();

// Window + channel state, host-observable via v-models.
const windowMode = defineModel<WindowMode>("mode", { default: "docked" });
const channel = defineModel<Channel>("channel", { default: "email" });

const channelLabel = computed(() => (channel.value === "comment" ? "Comment" : "Email"));
const submitLabel = computed(() => (channel.value === "comment" ? "Comment" : props.label));
const channelOptions = computed(() =>
	props.channels.map((value) => ({
		label: value === "comment" ? "Comment" : "Email",
		value,
	}))
);

// Two-way state, host-owned. (Attachments stay owned by the base — see `remove-attachment`.)
const body = defineModel<string>("body", { default: "" });
const recipients = defineModel<Recipients>("recipients", {
	default: () => ({ to: [], cc: [], bcc: [] }),
});
const subject = defineModel<string>("subject", { default: "" });

const composer = ref<InstanceType<typeof Composer> | null>(null);

// Switching channel (Email <-> Comment) starts a fresh message: clear the
// editor body, attachments, and any quoted reply so content doesn't bleed
// across types.
watch(channel, () => composer.value?.reset());

// Docked resize. `null` = size to content (default); a drag on the top grip
// pins a `min-height` so the docked window can grow taller. Using min-height
// (not height) means the panel still grows to fit its content — so toggling
// CC/BCC never clips the footer, and the content height is always the floor.
const dockedHeight = ref<number | null>(null);

const dockedStyle = computed(() =>
	windowMode.value === "docked" && dockedHeight.value
		? { minHeight: `${dockedHeight.value}px` }
		: undefined
);

// Drag the top edge up to grow the window (bottom is pinned by the host). Seed
// from the panel's current rendered height the first time, so there's no jump.
function startDockedResize(event: PointerEvent) {
	const panel = (event.currentTarget as HTMLElement).closest(".floating-window") as HTMLElement | null;
	const startY = event.clientY;
	const startHeight = dockedHeight.value ?? panel?.offsetHeight ?? 0;
	function onMove(moveEvent: PointerEvent) {
		const next = startHeight - (moveEvent.clientY - startY);
		dockedHeight.value = Math.min(Math.max(next, 0), window.innerHeight);
	}
	function onUp() {
		window.removeEventListener("pointermove", onMove);
		window.removeEventListener("pointerup", onUp);
	}
	window.addEventListener("pointermove", onMove);
	window.addEventListener("pointerup", onUp);
}

// To is always shown; Subject shows whenever `fields` includes it. Cc/Bcc stay
// hidden until revealed from the To-row toggles (or a prefilled value opens them).
const showSubject = computed(() => props.fields?.includes("subject") ?? false);
const showCc = ref(false);
const showBcc = ref(false);

function hasRecipients() {
	const { to, cc, bcc } = recipients.value;
	return Boolean(to.length || cc.length || bcc.length);
}

// The base hands us the body + attachments. Comment mode re-emits as
// `submit-comment`; email mode guards recipients, adds the envelope, and re-emits
// as `submit`. Bailing without emitting aborts the send, keeping the draft.
function handleSubmit({ body: message, attachments }: CoreSubmitPayload) {
	if (channel.value === "comment") {
		emit("submit-comment", { body: message, attachments });
		return;
	}
	if (!hasRecipients()) {
		toast.warning("Add at least one recipient before sending.");
		return;
	}
	emit("submit", {
		subject: subject.value,
		body: message,
		recipients: recipients.value,
		attachments,
	});
}

function resetFields() {
	recipients.value = { to: [], cc: [], bcc: [] };
	subject.value = "";
}

function reset() {
	resetFields();
	composer.value?.reset();
}

const editor = computed(() => composer.value?.editor);

defineExpose({
	editor,
	focus: () => composer.value?.focus(),
	reset,
	submit: () => composer.value?.submit(),
	// Drop a quoted message into the collapsible reply block. To pre-fill a reply,
	// set `v-model:recipients` and call this.
	setQuotedReply: (content: string) => composer.value?.setQuotedReply(content),
});
</script>
