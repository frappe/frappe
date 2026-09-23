<!-- The composer band at the foot of a tab that has one: the pill, or the open writer docked. -->
<template>
	<div
		v-if="shown"
		ref="band"
		class="pointer-events-none absolute inset-x-0 bottom-4 z-10 px-6"
		data-record-composer
	>
		<div class="mx-auto w-full max-w-3xl">
			<ComposerCard
				v-if="writer"
				:key="recordKey"
				:writer="writer"
				:user="user.name"
				@collapse="page.composer.close()"
			>
				<component
					:is="writer.component"
					v-if="writer.component"
					v-bind="{ ...writer.props, page, close }"
				/>
				<CommentWriter
					v-else-if="writer.name === COMMENT_WRITER"
					:key="commentRevision"
					:controller="controller"
					:user="user"
				/>
			</ComposerCard>
			<ComposerPill
				v-else
				:comment="comment"
				:creates="creates"
				:user="user"
				@open="page.composer.open($event)"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, onUnmounted, ref, watchEffect } from "vue";
import { useElementSize } from "@vueuse/core";
import type { SessionUser } from "@framework/ui/api";
import { isComposerTab, type RecordPageController } from "@/recordPage";
import type { TabItem } from "@/recordPage/types";
import { activeWriter, draftRevision } from "@/shell/composer";
import { RecordFeedsKey } from "../feed/recordFeeds";
import { COMMENT_WRITER } from "./commentDraft";
import ComposerCard from "./ComposerCard.vue";
import ComposerPill from "./ComposerPill.vue";
import CommentWriter from "./CommentWriter.vue";
import { createOptions } from "./createMenu";

const props = defineProps<{
	controller: RecordPageController;
	/** The strip's visible tabs, in strip order. */
	tabs: TabItem[];
	active: string;
	user: SessionUser;
}>();

const feeds = inject(RecordFeedsKey, null);
const band = ref<HTMLElement | null>(null);
const { height } = useElementSize(band, undefined, { box: "border-box" });

const page = computed(() => props.controller.page);
const recordKey = computed(() => JSON.stringify([page.value.doctype, page.value.docname]));
const writers = computed(() => props.controller.composer.visible());
const comment = computed(() => writers.value.find((item) => item.name === COMMENT_WRITER));
const writer = computed(() => {
	const open = activeWriter(page.value.doctype, page.value.docname);
	return open ? writers.value.find((item) => item.name === open) : undefined;
});
// A draft set from outside the writer, as a failed post does, draws in a fresh editor.
const commentRevision = computed(() =>
	draftRevision(page.value.doctype, page.value.docname, COMMENT_WRITER)
);
const creates = computed(() => createOptions(props.tabs, page.value));
const onComposerTab = computed(() => {
	const tab = props.tabs.find((item) => item.name === props.active);
	return Boolean(tab && isComposerTab(tab));
});
const shown = computed(
	() => onComposerTab.value && Boolean(writer.value || comment.value || creates.value.length)
);

watchEffect(() => measured(shown.value ? height.value : 0));
onUnmounted(() => measured(0));

function close() {
	page.value.composer.close();
}

function measured(pixels: number) {
	if (feeds) feeds.composerBand.value = pixels;
}
</script>
