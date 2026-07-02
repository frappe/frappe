<template>
	<!-- Email content: a From slot + recipient/subject rows above the shared editing
		 core. Window-agnostic by default; set `expandable` for a standalone collapsible
		 window (for a channel switcher instead, use MultiComposer). -->
	<ComposerWindow
		v-if="expandable"
		ref="windowRef"
		v-bind="$attrs"
		:expandable="true"
		:minimizable="false"
		:start-expanded="true"
		title="Email"
		:avatar="avatar"
		:avatar-label="avatarLabel"
		:placeholder="preview || placeholder"
	>
		<Composer
			ref="composer"
			:placeholder="placeholder"
			:label="label"
			:upload-function="uploadFunction"
			v-model:body="body"
			v-model:quoted="quoted"
			@submit="handleSubmit"
			@discard="emit('discard')"
			@remove-attachment="emit('remove-attachment', $event)"
		>
			<template #top>
				<slot name="from" />
				<RecipientFields
					v-model="recipients"
					v-model:subject="subject"
					:fields="fields"
					:search="searchRecipients"
				/>
			</template>

			<template v-if="$slots.actions" #actions="actionProps">
				<slot name="actions" v-bind="actionProps" />
			</template>
		</Composer>
	</ComposerWindow>

	<Composer
		v-else
		ref="composer"
		v-bind="$attrs"
		:placeholder="placeholder"
		:label="label"
		:upload-function="uploadFunction"
		v-model:body="body"
		v-model:quoted="quoted"
		@submit="handleSubmit"
		@discard="emit('discard')"
		@remove-attachment="emit('remove-attachment', $event)"
	>
		<!-- From picker + recipient rows. -->
		<template #top>
			<slot name="from" />
			<RecipientFields
				v-model="recipients"
				v-model:subject="subject"
				:fields="fields"
				:search="searchRecipients"
			/>
		</template>

		<!-- Host-supplied actions: wire a FileUploader to `addAttachment` / `setUploading`. -->
		<template v-if="$slots.actions" #actions="actionProps">
			<slot name="actions" v-bind="actionProps" />
		</template>
	</Composer>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { toast } from "frappe-ui";
import Composer from "../Composer.vue";
import ComposerWindow from "../ComposerWindow.vue";
import RecipientFields from "./RecipientFields.vue";
import { textPreview } from "../textPreview";
import type {
	CoreSubmitPayload,
	EmailComposerProps,
	EmailPayload,
	Recipients,
	UploadedFile,
} from "../types";

defineOptions({ inheritAttrs: false });

const props = withDefaults(defineProps<EmailComposerProps>(), {
	fields: () => ["cc", "bcc"],
	label: "Send",
});

const emit = defineEmits<{
	discard: [];
	"remove-attachment": [file: UploadedFile];
	/** Host runs the send and calls `reset()` (and `collapse()`, if windowed) itself
	 *  when done. */
	submit: [payload: EmailPayload];
}>();

// Host-owned two-way state (attachments stay owned by the core).
const body = defineModel<string>("body", { default: "" });
// Quoted reply HTML, surfaced so a host can preserve it across the window
// unmounting (collapse / channel switch); MultiComposer holds it.
const quoted = defineModel<string | null>("quoted", { default: null });
const recipients = defineModel<Recipients>("recipients", {
	default: () => ({ to: [], cc: [], bcc: [] }),
});
const subject = defineModel<string>("subject", { default: "" });

const composer = ref<InstanceType<typeof Composer> | null>(null);
const windowRef = ref<InstanceType<typeof ComposerWindow> | null>(null);
const preview = computed(() => textPreview(body.value));

function hasRecipients() {
	const { to, cc, bcc } = recipients.value;
	return Boolean(to.length || cc.length || bcc.length);
}

// Bailing without emitting `submit` aborts the send and keeps the draft.
function handleSubmit({ body: message, attachments }: CoreSubmitPayload) {
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

function reset() {
	recipients.value = { to: [], cc: [], bcc: [] };
	subject.value = "";
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
	// No-ops when `expandable` is false — there's no window to (un)collapse.
	expand: () => windowRef.value?.expand(),
	collapse: () => windowRef.value?.collapse(),
});
</script>
