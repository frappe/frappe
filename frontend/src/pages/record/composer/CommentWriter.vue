<!-- The built-in `comment` writer: the editor, loaded on first open, over the record's draft. -->
<template>
	<!-- The card sets the height, so the editor's own 50vh cap would strand its lower part. -->
	<div class="flex min-h-0 flex-1 flex-col [&_.composer-body]:!max-h-none" data-comment-writer>
		<CommentComposer
			ref="composer"
			v-model="content"
			class="min-h-0 flex-1"
			:placeholder="__('Write a comment…')"
			:submitLabel="__('Comment')"
			:uploadFunction="upload"
			:submitting="sent"
			@submit="send"
			@remove-attachment="forget"
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
import type { RecordPageController } from "@/recordPage";
import { __ } from "@/i18n";
import AttachmentSeed from "./AttachmentSeed";
import { postComment } from "./commentPost";
import { useCommentDraft } from "./useCommentDraft";

const CommentComposer = defineAsyncComponent(() =>
	import("@framework/ui/Composer").then((module) => module.CommentComposer)
);

const props = defineProps<{ controller: RecordPageController; user: SessionUser }>();

const { content, seed, upload, forget } = useCommentDraft(
	props.controller.page.doctype,
	props.controller.page.docname
);
const composer = ref<{ focus: () => void } | null>(null);
// A writer posts once; the band closes it, and a reopen draws a new one.
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
	void postComment(props.controller, author, {
		content: payload.body,
		attachments: [...payload.attachments],
	});
}
</script>
