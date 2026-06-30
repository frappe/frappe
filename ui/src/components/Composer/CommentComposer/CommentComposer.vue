<template>
	<!-- Internal comment: just the editing core, no recipients or subject. -->
	<Composer
		ref="composer"
		:placeholder="placeholder"
		:label="label"
		:loading="loading"
		:upload-function="uploadFunction"
		:mention-options="mentionOptions"
		v-model:body="body"
		@submit="emit('submit', $event)"
		@discard="emit('discard')"
		@remove-attachment="emit('remove-attachment', $event)"
	>
		<template #header>
			<ComposerHeader title="Comment" />
		</template>

		<template v-if="$slots.actions" #actions="actionProps">
			<slot name="actions" v-bind="actionProps" />
		</template>
	</Composer>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import Composer from "../Composer.vue";
import ComposerHeader from "../ComposerHeader.vue";
import type { CommentComposerProps, CommentPayload, UploadedFile } from "../types";

withDefaults(defineProps<CommentComposerProps>(), {
	placeholder: "This message is only visible to internal team.",
	label: "Comment",
});

const emit = defineEmits<{
	/** Posted comment (body + attachments). Run the send and call `reset()` on success. */
	submit: [payload: CommentPayload];
	discard: [];
	"remove-attachment": [file: UploadedFile];
}>();

const body = defineModel<string>("body", { default: "" });

const composer = ref<InstanceType<typeof Composer> | null>(null);
const editor = computed(() => composer.value?.editor);

defineExpose({
	editor,
	focus: () => composer.value?.focus(),
	reset: () => composer.value?.reset(),
	submit: () => composer.value?.submit(),
});
</script>
