<template>
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
		<!-- Providing #header replaces the built-in rows, even when empty. -->
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

const body = defineModel<string>({ default: "" });
const quoted = defineModel<string | null>("quoted", { default: null });
const recipients = defineModel<Recipients>("recipients", {
	default: () => ({ to: [], cc: [], bcc: [] }),
});
const subject = defineModel<string>("subject", { default: "" });
const from = defineModel<string>("from", { default: "" });

const core = ref<InstanceType<typeof ComposerEditor> | null>(null);

// No validation here — the host owns the send.
function handleSubmit({ body: message, attachments }: CoreSubmitPayload) {
	emit("submit", {
		from: from.value,
		subject: subject.value,
		body: message,
		recipients: recipients.value,
		attachments,
	});
}

// `from` survives reset — the sender identity carries over.
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
