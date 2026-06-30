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
		<TextEditor
			:content="comment.data.content"
			:editable="editable"
			editor-class="prose-sm"
			@change="editedContent = $event"
		/>
		<div v-if="editable" class="mt-2 flex justify-end gap-2">
			<Button variant="outline" label="Discard" @click="emit('discard')" />
			<Button variant="solid" label="Save" @click="emit('save', editedContent)" />
		</div>
		<slot v-else name="footer" :comment="comment" />
	</TimelineCard>
</template>

<script setup lang="ts">
import { Button, TextEditor } from "frappe-ui";
import { ref } from "vue";
import TimeAgo from "./TimeAgo.vue";
import TimelineCard from "./TimelineCard.vue";
import type { CommentActivity } from "./types";

const props = withDefaults(
	defineProps<{
		comment: CommentActivity;
		editable?: boolean;
	}>(),
	{
		editable: false,
	}
);

const emit = defineEmits<{
	save: [content: string];
	discard: [];
}>();

const editedContent = ref(props.comment.data.content);
</script>
