<template>
	<Composer
		ref="composer"
		:storage-key="storageKey"
		:placeholder="placeholder"
		:label="label"
		:upload-function="uploadFunction"
		:signature="signature"
		v-model:body="body"
		:on-submit="handleSubmit"
		@discard="emit('discard')"
		@submitted="resetFields"
		@remove-attachment="emit('remove-attachment', $event)"
	>
		<template #header>
			<ComposerHeader title="Email">
				<template #actions>
					<FieldToggles
						:optional-fields="optionalFields"
						:show-cc="showCc"
						:show-bcc="showBcc"
						@toggle-cc="showCc = !showCc"
						@toggle-bcc="showBcc = !showBcc"
					/>
				</template>
			</ComposerHeader>
		</template>

		<template #top>
			<!-- Leading content above the recipient rows — a host drops a
				 From / identity picker here (e.g. mail's outgoing-address select). -->
			<slot name="from" />
			<RecipientFields
				v-model="recipients"
				v-model:subject="subject"
				:show-subject="showSubject"
				:show-cc="showCc"
				:show-bcc="showBcc"
			/>
		</template>

		<!-- Attachments, canned-response pickers, etc. are host-supplied: wire a
			 FileUploader to `addAttachment` and report progress via `setUploading`. -->
		<template v-if="$slots.utilities" #utilities="utilityProps">
			<slot name="utilities" v-bind="utilityProps" />
		</template>
	</Composer>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { toast } from "frappe-ui";
import Composer from "../Composer.vue";
import ComposerHeader from "../ComposerHeader.vue";
import FieldToggles from "./FieldToggles.vue";
import RecipientFields from "./RecipientFields.vue";
import type { CoreSubmitPayload, EmailComposerProps, Recipients, UploadedFile } from "../types";

const props = withDefaults(defineProps<EmailComposerProps>(), {
	optionalFields: () => ["cc", "bcc"],
});

const emit = defineEmits<{
	discard: [];
	"remove-attachment": [file: UploadedFile];
}>();

// Two-way state, host-owned. Seed and observe via v-models; defaults make them
// optional. (Attachments stay owned by the base — see `remove-attachment`.)
const body = defineModel<string>("body", { default: "" });
const recipients = defineModel<Recipients>("recipients", {
	default: () => ({ to: [], cc: [], bcc: [] }),
});
const subject = defineModel<string>("subject", { default: "" });

const composer = ref<InstanceType<typeof Composer> | null>(null);

// To is always shown; Subject shows whenever `optionalFields` includes it.
// Cc/Bcc stay hidden until revealed from the header (or a prefilled value opens them).
const showSubject = computed(() => props.optionalFields.includes("subject"));
const showCc = ref(false);
const showBcc = ref(false);

function hasRecipients() {
	const { to, cc, bcc } = recipients.value;
	return Boolean(to.length || cc.length || bcc.length);
}

// The base hands us the body + attachments; we guard recipients, add the email
// envelope, and pass it on. Throwing aborts the submit and keeps the draft.
async function handleSubmit({ body: message, attachments }: CoreSubmitPayload) {
	if (!hasRecipients()) {
		toast.warning("Add at least one recipient before sending.");
		throw new Error("EmailComposer: no recipients");
	}
	await props.onSubmit?.({
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
	// Drop a quoted message into the collapsible reply block. To pre-fill a
	// reply, set `v-model:recipients` and call this.
	setQuotedReply: (content: string) => composer.value?.setQuotedReply(content),
});
</script>
