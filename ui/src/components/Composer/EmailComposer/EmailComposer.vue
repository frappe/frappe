<template>
	<!-- A standalone, inline email composer: a From slot plus recipient and subject
		 rows above the shared editing core. Emits an EmailPayload on send — the host
		 performs the actual send, then calls reset(). -->
	<ComposerEditor
		ref="core"
		:placeholder="placeholder"
		:submit-label="submitLabel"
		:upload-function="uploadFunction"
		v-model:body="body"
		v-model:quoted="quoted"
		@submit="handleSubmit"
		@remove-attachment="emit('remove-attachment', $event)"
	>
		<!-- From picker + recipient rows. -->
		<template #top>
			<slot name="from" />
			<RecipientFields
				v-if="!hideRecipients"
				v-model="recipients"
				v-model:subject="subject"
				:fields="fields"
				:search="searchRecipients"
			/>
		</template>

		<!-- Extra footer actions. Attachments already have a built-in button (pass
			 `uploadFunction`); this slot is for anything more, and still exposes
			 `addAttachment` / `setUploading` for a fully custom uploader. -->
		<template v-if="$slots.actions" #actions="actionProps">
			<slot name="actions" v-bind="actionProps" />
		</template>
	</ComposerEditor>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { toast } from "frappe-ui";
import ComposerEditor from "../ComposerEditor.vue";
import RecipientFields from "./RecipientFields.vue";
import type {
	CoreSubmitPayload,
	EmailComposerEmits,
	EmailComposerProps,
	EmailComposerSlots,
	Recipients,
} from "../types";

withDefaults(defineProps<EmailComposerProps>(), {
	fields: () => ["cc", "bcc"],
	submitLabel: "Send",
});

const emit = defineEmits<EmailComposerEmits>();
defineSlots<EmailComposerSlots>();

// Two-way state, all optional to bind — the host owns each piece via v-model.
const body = defineModel<string>({ default: "" });
// Quoted reply HTML, shown as a collapsible block and appended back on send.
// Seed it (and clear `v-model`) to pre-fill a reply.
const quoted = defineModel<string | null>("quoted", { default: null });
const recipients = defineModel<Recipients>("recipients", {
	default: () => ({ to: [], cc: [], bcc: [] }),
});
const subject = defineModel<string>("subject", { default: "" });

const core = ref<InstanceType<typeof ComposerEditor> | null>(null);

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
	core.value?.reset();
}

defineExpose({
	editor: computed(() => core.value?.editor),
	focus: () => core.value?.focus(),
	reset,
	submit: () => core.value?.submit(),
});
</script>
