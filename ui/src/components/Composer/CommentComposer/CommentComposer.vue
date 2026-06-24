<template>
	<!-- An internal comment: just the editing core, no recipients or subject. The
		 consumer's send method receives `{ body, attachments }` straight from the
		 base composer. -->
	<Composer
		ref="composer"
		:storage-key="storageKey"
		:placeholder="placeholder"
		:label="label"
		:upload-function="uploadFunction"
		:mentions="mentions"
		v-model:body="body"
		:on-submit="onSubmit"
		@discard="emit('discard')"
		@remove-attachment="emit('remove-attachment', $event)"
	>
		<template #header>
			<ComposerHeader title="Comment" />
		</template>

		<template v-if="$slots.utilities" #utilities="utilityProps">
			<slot name="utilities" v-bind="utilityProps" />
		</template>
	</Composer>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import Composer from "../Composer.vue";
import ComposerHeader from "../ComposerHeader.vue";
import type { CommentComposerProps, UploadedFile } from "../types";

withDefaults(defineProps<CommentComposerProps>(), {
	storageKey: null,
	placeholder: "This message is only visible to internal team.",
	label: "Comment",
});

const emit = defineEmits<{
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
