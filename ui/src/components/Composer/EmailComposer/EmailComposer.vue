<template>
	<!--
		An email composer that owns its window: it wraps itself in a FloatingWindow
		so the title, field toggles, and float/dock control share one bar that
		doubles as the title bar / drag handle. `v-model:mode` drives docked /
		floating / minimized. Pass more than one `channel` (e.g. ["email", "comment"])
		to turn the title into a switcher and gain a `submit-comment` event.
	-->
	<FloatingWindow v-model:mode="windowMode" :minimizable="true">
		<template #header="{ mode, float, dock, minimize, expandFromTray }">
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
				<!-- Multi-channel: the title becomes an Email/Comment switcher. -->
				<template v-if="channels.length > 1" #title>
					<div class="flex gap-[4px] items-center">
						<span class="text-ink-gray-5 text-base">Via</span>
						<Dropdown :options="channelOptions" placement="bottom-start">
							<button
								class="flex items-center gap-1 rounded px-1.5 py-0.5 text-base text-ink-gray-7 hover:bg-surface-gray-2"
							>
								{{ channelLabel }}
								<FeatherIcon name="chevron-down" class="h-4 w-4 text-ink-gray-5" />
							</button>
						</Dropdown>
					</div>
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
import { computed, ref } from "vue";
import { Button, Dropdown, FeatherIcon, toast } from "frappe-ui";
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
		onClick: () => (channel.value = value),
	}))
);

// Two-way state, host-owned. (Attachments stay owned by the base — see `remove-attachment`.)
const body = defineModel<string>("body", { default: "" });
const recipients = defineModel<Recipients>("recipients", {
	default: () => ({ to: [], cc: [], bcc: [] }),
});
const subject = defineModel<string>("subject", { default: "" });

const composer = ref<InstanceType<typeof Composer> | null>(null);

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
