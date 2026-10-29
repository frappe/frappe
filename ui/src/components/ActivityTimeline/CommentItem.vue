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

		<CommentEditor
			v-if="editable"
			:content="comment.data.content"
			:editorClass="editorClass"
			:uploadFunction="uploadFunction"
			@save="emit('save', $event)"
			@discard="emit('discard')"
		/>
		<RichTextView v-else :html="comment.data.content" :class="editorClass" />
		<slot v-if="!editable" name="footer" :comment="comment">
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
import { defineAsyncComponent, h } from "vue";
import RichTextView from "../RichText/RichTextView.vue";
import AttachmentChip from "./AttachmentChip.vue";
import TimeAgo from "./TimeAgo.vue";
import TimelineCard from "./TimelineCard.vue";
import type { CommentItemProps } from "./types";

// While the editor's chunk loads, or if it fails to, the saved comment holds its place.
const SavedComment = (props: { content: string; editorClass?: string }) =>
	h(RichTextView, { html: props.content, class: props.editorClass });
const CommentEditor = defineAsyncComponent({
	loader: () => import("./CommentEditor.vue"),
	loadingComponent: SavedComment,
	errorComponent: SavedComment,
	delay: 0,
});

withDefaults(defineProps<CommentItemProps>(), {
	editable: false,
	editorClass: "prose-sm max-w-none",
});

const emit = defineEmits<{
	save: [content: string];
	discard: [];
}>();
</script>
