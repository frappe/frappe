<!-- The built-in `comment` writer: the editor, loaded on first open, over the record's draft. -->
<template>
	<div class="flex min-h-0 flex-1 flex-col" data-comment-writer>
		<CommentComposer
			ref="composer"
			v-model="content"
			class="min-h-0 flex-1"
			:placeholder="__('Write a comment…')"
			:submitLabel="__('Comment')"
			:uploadFunction="upload"
			:submitting="sent"
			fill
			@submit="send"
			@remove-attachment="forget"
			@discard="discard"
		>
			<template #actions="{ addAttachment }">
				<AttachmentSeed :files="seed" :add="addAttachment" />
			</template>
		</CommentComposer>
	</div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref, watch } from "vue";
import type { SessionUser } from "@framework/ui/api";
import type { CommentPayload } from "@framework/ui/Composer";
import type { WriterContext } from "@/shell/composer";
import { __ } from "@/i18n";
import AttachmentSeed from "./AttachmentSeed";
import { postComment } from "./commentPost";
import { useCommentDraft } from "./useCommentDraft";

const CommentComposer = defineAsyncComponent(() =>
	import("@framework/ui/Composer").then((module) => module.CommentComposer)
);

const props = defineProps<{ context: WriterContext; user: SessionUser }>();

const { content, seed, upload, forget, discard } = useCommentDraft(
	props.context.doctype,
	props.context.docname
);
const composer = ref<{ focus: () => void } | null>(null);
// A writer posts once; the post closes it, and a reopen draws a new one.
const sent = ref(false);

watch(composer, (editor) => editor?.focus());

function send(payload: CommentPayload) {
	if (sent.value) return;
	sent.value = true;
	const author = {
		name: props.user.name,
		email: props.user.email,
		fullname: props.user.full_name,
		image: props.user.user_image ?? undefined,
	};
	void postComment(props.context, author, {
		content: payload.body,
		attachments: [...payload.attachments],
	});
}
</script>
