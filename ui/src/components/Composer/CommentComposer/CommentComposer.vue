<template>
	<ComposerEditor
		ref="core"
		:placeholder="placeholder"
		:submit-label="submitLabel"
		:upload-function="uploadFunction"
		:extensions="extensions"
		:mentions="mentions"
		v-model:body="body"
		@submit="emit('submit', $event)"
		@remove-attachment="emit('remove-attachment', $event)"
	>
		<template v-if="$slots.actions" #actions="actionProps">
			<slot name="actions" v-bind="actionProps" />
		</template>
	</ComposerEditor>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import ComposerEditor from "../ComposerEditor.vue";
import type { CommentComposerEmits, CommentComposerProps, CommentComposerSlots } from "../types";

withDefaults(defineProps<CommentComposerProps>(), {
	placeholder: "This message is only visible to your team.",
	submitLabel: "Comment",
});

const emit = defineEmits<CommentComposerEmits>();
defineSlots<CommentComposerSlots>();

const body = defineModel<string>({ default: "" });

const core = ref<InstanceType<typeof ComposerEditor> | null>(null);

defineExpose({
	editor: computed(() => core.value?.editor),
	focus: () => core.value?.focus(),
	reset: () => core.value?.reset(),
	submit: () => core.value?.submit(),
});
</script>
