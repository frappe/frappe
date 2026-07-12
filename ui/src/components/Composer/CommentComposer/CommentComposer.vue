<template>
	<!-- A standalone, inline comment composer: the shared editing core with
		 @-mentions, for internal notes. Emits a CommentPayload on send — the host
		 performs the send, then calls reset(). -->
	<ComposerEditor
		ref="core"
		:placeholder="placeholder"
		:submit-label="submitLabel"
		:upload-function="uploadFunction"
		:mentions="mentions"
		v-model:body="body"
		@submit="emit('submit', $event)"
		@remove-attachment="emit('remove-attachment', $event)"
	>
		<!-- Extra footer actions. Attachments already have a built-in button (pass
			 `uploadFunction`); this slot is for anything more, and still exposes
			 `addAttachment` / `setUploading` for a fully custom uploader. -->
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
	placeholder: "This message is only visible to internal team.",
	submitLabel: "Comment",
});

const emit = defineEmits<CommentComposerEmits>();
defineSlots<CommentComposerSlots>();

// The comment draft; optional to bind — the host owns it via v-model.
const body = defineModel<string>({ default: "" });

const core = ref<InstanceType<typeof ComposerEditor> | null>(null);

defineExpose({
	editor: computed(() => core.value?.editor),
	focus: () => core.value?.focus(),
	reset: () => core.value?.reset(),
	submit: () => core.value?.submit(),
});
</script>
