<template>
	<!-- Email content: a From slot + recipient/subject rows above the shared
		 editing core. Window-agnostic; for a channel switcher use MultiComposer. -->
	<Composer
		ref="composer"
		:placeholder="placeholder"
		:label="label"
		:upload-function="uploadFunction"
		:on-submit="handleSubmit"
		v-model:body="body"
		v-model:quoted="quoted"
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
import RecipientFields from "./RecipientFields.vue";
import type { CoreSubmitPayload, EmailComposerProps, Recipients, UploadedFile } from "../types";

const props = withDefaults(defineProps<EmailComposerProps>(), {
	fields: () => ["cc", "bcc"],
	label: "Send",
});

const emit = defineEmits<{
	discard: [];
	"remove-attachment": [file: UploadedFile];
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

function hasRecipients() {
	const { to, cc, bcc } = recipients.value;
	return Boolean(to.length || cc.length || bcc.length);
}

// Bailing without calling onSubmit aborts the send and keeps the draft.
async function handleSubmit({ body: message, attachments }: CoreSubmitPayload) {
	if (!hasRecipients()) {
		toast.warning("Add at least one recipient before sending.");
		return;
	}
	await props.onSubmit({
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
});
</script>
