<template>
	<!-- Internal comment: just the editing core, no recipients or subject.
		 Window-agnostic; for a channel switcher use MultiComposer. -->
	<Composer
		ref="composer"
		:placeholder="placeholder"
		:label="label"
		:upload-function="uploadFunction"
		:mention-options="mentionOptions"
		:on-submit="onSubmit"
		v-model:body="body"
		@discard="emit('discard')"
		@remove-attachment="emit('remove-attachment', $event)"
	>
		<template v-if="$slots.actions" #actions="actionProps">
			<slot name="actions" v-bind="actionProps" />
		</template>
	</Composer>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import Composer from "../Composer.vue";
import type { CommentComposerProps, UploadedFile } from "../types";

const props = withDefaults(defineProps<CommentComposerProps>(), {
	placeholder: "This message is only visible to internal team.",
	label: "Comment",
});

const emit = defineEmits<{
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
