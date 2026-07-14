<template>
	<!-- A standalone, inline email composer: header rows (From/Subject/To/Cc/Bcc,
		 per `headerFields`) above the shared editing core. Emits an EmailPayload on send —
		 the host performs the actual send, then calls reset(). -->
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
		<!-- Built-in header rows; providing #header replaces them, even empty
			 (which renders no header at all). -->
		<template #top>
			<slot v-if="$slots.header" name="header" />
			<HeaderFields
				v-else-if="headerFields.length"
				v-model="recipients"
				v-model:subject="subject"
				v-model:from="from"
				:fields="headerFields"
				:senders="senders"
				:search="searchRecipients"
			/>
		</template>

		<!-- Extra footer actions; slot props drive a custom uploader. -->
		<template v-if="$slots.actions" #actions="actionProps">
			<slot name="actions" v-bind="actionProps" />
		</template>
	</ComposerEditor>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import ComposerEditor from "../ComposerEditor.vue";
import HeaderFields from "./HeaderFields.vue";
import type {
	CoreSubmitPayload,
	EmailComposerEmits,
	EmailComposerProps,
	EmailComposerSlots,
	Recipients,
} from "../types";

withDefaults(defineProps<EmailComposerProps>(), {
	headerFields: () => ["to", "cc", "bcc"],
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
const from = defineModel<string>("from", { default: "" });

const core = ref<InstanceType<typeof ComposerEditor> | null>(null);

// No recipient validation here — the host owns the send and can decline it.
function handleSubmit({ body: message, attachments }: CoreSubmitPayload) {
	emit("submit", {
		from: from.value,
		subject: subject.value,
		body: message,
		recipients: recipients.value,
		attachments,
	});
}

// `from` survives a reset — the sender identity carries over to the next email.
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
