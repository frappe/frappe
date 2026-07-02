<template>
	<!-- Internal comment: just the editing core, no recipients or subject. Window-agnostic
		 by default; set `expandable` for a standalone collapsible window (for a channel
		 switcher instead, use MultiComposer). -->
	<ComposerWindow
		v-if="expandable"
		ref="windowRef"
		v-bind="$attrs"
		:expandable="true"
		:minimizable="false"
		:start-expanded="true"
		title="Comment"
		:avatar="avatar"
		:avatar-label="avatarLabel"
		:placeholder="preview || placeholder"
	>
		<Composer
			ref="composer"
			:placeholder="placeholder"
			:label="label"
			:upload-function="uploadFunction"
			:mention-options="mentionOptions"
			v-model:body="body"
			@submit="emit('submit', $event)"
			@discard="emit('discard')"
			@remove-attachment="emit('remove-attachment', $event)"
		>
			<template v-if="$slots.actions" #actions="actionProps">
				<slot name="actions" v-bind="actionProps" />
			</template>
		</Composer>
	</ComposerWindow>

	<Composer
		v-else
		ref="composer"
		v-bind="$attrs"
		:placeholder="placeholder"
		:label="label"
		:upload-function="uploadFunction"
		:mention-options="mentionOptions"
		v-model:body="body"
		@submit="emit('submit', $event)"
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
import ComposerWindow from "../ComposerWindow.vue";
import { textPreview } from "../textPreview";
import type { CommentComposerProps, CommentPayload, UploadedFile } from "../types";

defineOptions({ inheritAttrs: false });

withDefaults(defineProps<CommentComposerProps>(), {
	placeholder: "This message is only visible to internal team.",
	label: "Comment",
});

const emit = defineEmits<{
	discard: [];
	"remove-attachment": [file: UploadedFile];
	/** Host runs the send and calls `reset()` (and `collapse()`, if windowed) itself
	 *  when done. */
	submit: [payload: CommentPayload];
}>();

const body = defineModel<string>("body", { default: "" });

const composer = ref<InstanceType<typeof Composer> | null>(null);
const windowRef = ref<InstanceType<typeof ComposerWindow> | null>(null);
const editor = computed(() => composer.value?.editor);
const preview = computed(() => textPreview(body.value));

defineExpose({
	editor,
	focus: () => composer.value?.focus(),
	reset: () => composer.value?.reset(),
	submit: () => composer.value?.submit(),
	// No-ops when `expandable` is false — there's no window to (un)collapse.
	expand: () => windowRef.value?.expand(),
	collapse: () => windowRef.value?.collapse(),
});
</script>
