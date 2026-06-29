<template>
	<!-- An internal comment: just the editing core, no recipients or subject. The
		 consumer's send method receives `{ body, attachments }` straight from the
		 base composer. -->
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
	/** The user posted the comment (body + attachments). Run the send (set
	 *  `:loading` while it does) and call the exposed `reset()` on success. */
	submit: [payload: CommentPayload];
	discard: [];
	"remove-attachment": [file: UploadedFile];
}>();

// `v-model:body` forwarded to the base so a host can seed and observe the body.
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
