<template>
	<TimelineCard content-class="bg-surface-gray-1 p-3">
		<template #header>
			<div class="ps-3" :class="$slots.actions && !editable ? 'pe-1.5' : 'pe-3'">
				<slot name="header" :comment="comment">
					<!-- 40px header; center aligns with the gutter avatar -->
					<div class="flex h-10 items-center justify-between gap-2">
						<div class="leading-6">
							<span class="text-base font-medium text-ink-gray-6">{{
								comment.author.fullname
							}}</span>
						</div>
						<div class="flex items-center gap-2">
							<TimeAgo :timestamp="comment.timestamp" class="text-sm" />
							<div
								v-if="$slots.actions && !editable"
								class="flex items-center gap-1"
							>
								<slot name="actions" />
							</div>
						</div>
					</div>
				</slot>
			</div>
		</template>

		<!-- content -->
		<div
			@keydown.ctrl.enter="editable && emit('save', editedContent)"
			@keydown.meta.enter="editable && emit('save', editedContent)"
		>
			<Editor
				ref="editorRef"
				v-model="editedContent"
				:extensions="extensions"
				:editable="editable"
				:upload-function="uploadFunction"
			>
				<EditorContent :class="editorClass" />
			</Editor>
		</div>
		<div v-if="editable" class="mt-2 flex justify-end gap-2">
			<Button variant="outline" label="Discard" @click="emit('discard')" />
			<Button variant="solid" label="Save" @click="emit('save', editedContent)" />
		</div>
		<slot v-else name="footer" :comment="comment">
			<div v-if="comment.data.attachments?.length" class="mt-2 flex flex-wrap gap-2">
				<AttachmentChip
					v-for="a in comment.data.attachments"
					:key="a.file_url"
					:label="a.file_name"
					:url="a.file_url"
				/>
			</div>
		</slot>
	</TimelineCard>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { CommentKit, Editor, EditorContent } from "frappe-ui/editor";
import "frappe-ui/editor-style.css";
import { nextTick, ref, watch } from "vue";
import AttachmentChip from "./AttachmentChip.vue";
import TimeAgo from "./TimeAgo.vue";
import TimelineCard from "./TimelineCard.vue";
import type { CommentItemProps } from "./types";

const props = withDefaults(defineProps<CommentItemProps>(), {
	editable: false,
	editorClass: "prose-sm max-w-none",
});

const emit = defineEmits<{
	save: [content: string];
	discard: [];
}>();

const extensions = [CommentKit];
const editorRef = ref<InstanceType<typeof Editor> | null>(null);
const editedContent = ref(props.comment.data.content);

// entering edit starts from the saved content; leaving it (discard) reverts to it.
// setContent directly — a v-model reset can lose to the update setEditable emits
watch(
	() => props.editable,
	(editing) => {
		editedContent.value = props.comment.data.content;
		editorRef.value?.editor?.commands.setContent(props.comment.data.content);
		if (editing) nextTick(focusEditor);
	}
);

function focusEditor() {
	const editor = editorRef.value?.editor;
	if (!editor) return;
	editor.commands.focus("end");
	editor.view.focus();
	setTimeout(() => {
		if (!editor.isFocused) editor.view.focus();
	}, 200);
}

// saves / live updates refresh the read view
watch(
	() => props.comment.data.content,
	(content) => {
		if (!props.editable) editedContent.value = content;
	}
);
</script>
