<template>
	<!-- Email composer that owns its window via FloatingWindow. `v-model:mode`
		 drives docked/floating/minimized; pass multiple `channels` to turn the
		 title into a switcher and gain a `submit-comment` event. -->
	<!-- `:style` falls through onto FloatingWindow's panel; docked uses it to pin a
		 draggable height (undefined while floating/minimized). -->
	<FloatingWindow v-model:mode="windowMode" :minimizable="true" :style="dockedStyle">
		<template #header="{ mode, float, dock, minimize, expandFromTray }">
			<!-- Docked-only grip: drag up to grow the compose area (host pins the bottom). -->
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

				<!-- Cc/Bcc toggles: email-only, hidden while minimized. -->
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
			<!-- Email-only: From picker + recipient rows (comment mode is just the core). -->
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

			<!-- Host-supplied actions: wire a FileUploader to `addAttachment` / `setUploading`. -->
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

// Host-owned two-way state (attachments stay owned by the base).
const body = defineModel<string>("body", { default: "" });
const recipients = defineModel<Recipients>("recipients", {
	default: () => ({ to: [], cc: [], bcc: [] }),
});
const subject = defineModel<string>("subject", { default: "" });

const composer = ref<InstanceType<typeof Composer> | null>(null);

// Switching channel starts a fresh message.
watch(channel, () => composer.value?.reset());

// Docked resize: `null` sizes to content; a grip drag pins a `min-height` (not
// height, so content still grows the panel — toggling CC/BCC never clips).
const dockedHeight = ref<number | null>(null);

const dockedStyle = computed(() =>
	windowMode.value === "docked" && dockedHeight.value
		? { minHeight: `${dockedHeight.value}px` }
		: undefined
);

// Drag up to grow the window; seed from the rendered height so there's no jump.
function startDockedResize(event: PointerEvent) {
	const panel = (event.currentTarget as HTMLElement).closest(
		".floating-window"
	) as HTMLElement | null;
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

// Subject shows when `fields` includes it; Cc/Bcc stay hidden until toggled or prefilled.
const showSubject = computed(() => props.fields?.includes("subject") ?? false);
const showCc = ref(false);
const showBcc = ref(false);

function hasRecipients() {
	const { to, cc, bcc } = recipients.value;
	return Boolean(to.length || cc.length || bcc.length);
}

// Comment mode re-emits as `submit-comment`; email mode guards recipients and
// adds the envelope. Bailing without emitting aborts the send, keeping the draft.
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
