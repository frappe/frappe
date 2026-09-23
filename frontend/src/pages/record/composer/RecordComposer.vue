<!--
  The composer band at the foot of a tab that has one: the pill, and the place the shell docks
  the open writer.
-->
<template>
	<div
		v-if="shown"
		ref="band"
		class="pointer-events-none absolute inset-x-0 bottom-4 z-10 px-6"
		data-record-composer
	>
		<div class="mx-auto w-full max-w-3xl">
			<div ref="dock" data-composer-dock />
			<ComposerPill
				v-if="!docked"
				:comment="comment"
				:email="email"
				:creates="creates"
				:user="user"
				:title="title"
				@open="page.composer.open($event)"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, onUnmounted, ref, watch, watchEffect } from "vue";
import { useElementSize } from "@vueuse/core";
import type { SessionUser } from "@framework/ui/api";
import { isComposerTab, type RecordPageController } from "@/recordPage";
import type { TabItem } from "@/recordPage/types";
import { activeWriter, composerState, registerComposerDock } from "@/shell/composer";
import { RecordFeedsKey } from "../feed/recordFeeds";
import { COMMENT_WRITER } from "./commentDraft";
import { EMAIL_WRITER } from "./emailDraft";
import { titleOf } from "./emailSeed";
import ComposerPill from "./ComposerPill.vue";
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
const dock = ref<HTMLElement | null>(null);
const { height } = useElementSize(band, undefined, { box: "border-box" });

const page = computed(() => props.controller.page);
const writers = computed(() => props.controller.composer.visible());
const comment = computed(() => writers.value.find((item) => item.name === COMMENT_WRITER));
const email = computed(() => writers.value.find((item) => item.name === EMAIL_WRITER));
const writer = computed(() => {
	const open = activeWriter(page.value.doctype, page.value.docname);
	return open ? writers.value.find((item) => item.name === open) : undefined;
});
// The pill stays while this record's writer floats.
const docked = computed(() => Boolean(writer.value) && composerState.window === "docked");
const creates = computed(() => createOptions(props.tabs, page.value));
const title = computed(() => titleOf(page.value));
const onComposerTab = computed(() => {
	const tab = props.tabs.find((item) => item.name === props.active);
	return Boolean(tab && isComposerTab(tab));
});
const shown = computed(
	() =>
		onComposerTab.value &&
		Boolean(writer.value || comment.value || email.value || creates.value.length)
);

watchEffect(() => measured(shown.value ? height.value : 0));
onUnmounted(() => measured(0));

// Offered while the band is shown, so docking moves the open writer in without drawing it anew.
watch([dock, page], ([element, { doctype, docname }], _old, onCleanup) => {
	if (element) onCleanup(registerComposerDock(doctype, docname, element));
});

function measured(pixels: number) {
	if (feeds) feeds.composerBand.value = pixels;
}
</script>
