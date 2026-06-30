<template>
	<!-- mirrors EmailItem's card -->
	<div
		class="grow cursor-pointer overflow-hidden rounded-md border border-outline-gray-2 bg-surface-white text-base leading-6 transition-all duration-300 ease-in-out"
	>
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
						<Tooltip :text="dateFormat(comment.timestamp)">
							<p class="text-xs text-ink-gray-5 md:text-sm">
								{{ timeAgo(comment.timestamp) }}
							</p>
						</Tooltip>
						<div v-if="$slots.actions && !editable" class="flex items-center gap-1">
							<slot name="actions" />
						</div>
					</div>
				</div>
			</slot>
		</div>
		<hr class="border-t border-outline-gray-modals" />
		<!-- content region: gray, email-body padding -->
		<div class="bg-surface-gray-1 p-3">
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
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, TextEditor, Tooltip } from "frappe-ui";
import { ref } from "vue";
import type { CommentActivity } from "./types";
import { dateFormat, timeAgo } from "./utils";

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
