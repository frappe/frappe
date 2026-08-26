<template>
	<ComposerEditor
		ref="core"
		:placeholder="placeholder"
		:submit-label="submitLabel"
		:upload-function="uploadFunction"
		:extensions="extensions"
		v-model:body="body"
		v-model:quoted="quoted"
		@submit="handleSubmit"
		@remove-attachment="emit('remove-attachment', $event)"
	>
		<!-- Providing #header replaces the built-in rows, even when empty. -->
		<template #top>
			<slot v-if="$slots.header" name="header" />
			<HeaderFields
				v-else-if="hasHeader"
				v-model:to="to"
				v-model:cc="cc"
				v-model:bcc="bcc"
				v-model:subject="subject"
				v-model:from="from"
				:show-to="showTo"
				:show-cc="showCc"
				:show-bcc="showBcc"
				:show-from="showFrom"
				:show-subject="showSubject"
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
	Recipient,
} from "../types";

const props = withDefaults(defineProps<EmailComposerProps>(), {
	showTo: true,
	showCc: true,
	showBcc: true,
	showFrom: false,
	showSubject: false,
});

const hasHeader = computed(
	() => props.showTo || props.showCc || props.showBcc || props.showFrom || props.showSubject
);

const emit = defineEmits<EmailComposerEmits>();
defineSlots<EmailComposerSlots>();

const body = defineModel<string>({ default: "" });
const quoted = defineModel<string | null>("quoted", { default: null });
const to = defineModel<Recipient[]>("to", { default: () => [] });
const cc = defineModel<Recipient[]>("cc", { default: () => [] });
const bcc = defineModel<Recipient[]>("bcc", { default: () => [] });
const subject = defineModel<string>("subject", { default: "" });
const from = defineModel<string>("from", { default: "" });

const core = ref<InstanceType<typeof ComposerEditor> | null>(null);

// No validation here — the host owns the send.
function handleSubmit({ body: message, attachments }: CoreSubmitPayload) {
	emit("submit", {
		from: from.value,
		subject: subject.value,
		body: message,
		to: to.value,
		cc: cc.value,
		bcc: bcc.value,
		attachments,
	});
}

// `from` survives reset — the sender identity carries over.
function reset() {
	to.value = [];
	cc.value = [];
	bcc.value = [];
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
