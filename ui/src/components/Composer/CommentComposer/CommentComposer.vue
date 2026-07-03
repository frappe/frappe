<template>
	<!-- Internal comment: just the editing core, no recipients or subject. Renders
		 inline on its own; wrap it in <ComposerChannel> inside a <Composer> to make
		 it a windowed channel. -->
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
import { textPreview } from "../textPreview";
import { useComposerSurface } from "../composerContext";
import type { CommentComposerProps, CommentPayload, UploadedFile } from "../types";

withDefaults(defineProps<CommentComposerProps>(), {
	placeholder: "This message is only visible to internal team.",
	submitLabel: "Comment",
});

const emit = defineEmits<{
	"remove-attachment": [file: UploadedFile];
	/** Host runs the send, then calls `reset()` (and closes the window) itself. */
	submit: [payload: CommentPayload];
}>();

// The comment draft; optional to bind — it survives channel switches and window
// close (an enclosing Composer keeps channels mounted).
const body = defineModel<string>({ default: "" });

const core = ref<InstanceType<typeof ComposerEditor> | null>(null);

// Hand the draft preview + focus to an enclosing <ComposerChannel>, if any.
useComposerSurface({
	preview: () => textPreview(body.value),
	focus: () => core.value?.focus(),
});

defineExpose({
	editor: computed(() => core.value?.editor),
	focus: () => core.value?.focus(),
	reset: () => core.value?.reset(),
	submit: () => core.value?.submit(),
});
</script>
