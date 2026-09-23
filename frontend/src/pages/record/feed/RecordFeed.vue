<!-- The scroller a feed tab fills: a centred column, both edge fades and the jump button.
     With `paginate`, older rows load as the reader nears the top, and the view holds still. -->
<template>
	<!-- `flex-1` fills the tab body's column; the absolute scroller adds no height of its own. -->
	<div class="relative min-h-0 flex-1" data-record-feed>
		<!-- The scroll area's root sets an inline `position: relative`, so a wrapper holds the sizing.
		     `isolate` keeps the timeline's own z-indices under the fades. -->
		<div class="absolute inset-0 isolate">
			<ScrollArea ref="area" class="h-full" viewportClass="px-6 pb-8 pt-4">
				<!-- Hidden for the one frame between drawing the rows and landing at the bottom. -->
				<div
					ref="content"
					class="mx-auto flex w-full max-w-3xl flex-col gap-5"
					:class="{ invisible: ready && !landed }"
				>
					<div v-if="stalled" class="flex justify-center">
						<Button
							variant="ghost"
							iconLeft="lucide-refresh-cw"
							:label="__('Load older')"
							@click="retry"
						/>
					</div>
					<slot />
				</div>
			</ScrollArea>
		</div>

		<div
			class="pointer-events-none absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-surface-base to-transparent transition-opacity"
			:class="atTop ? 'opacity-0' : 'opacity-100'"
		/>
		<div
			class="pointer-events-none absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-surface-base to-transparent transition-opacity"
			:class="atBottom ? 'opacity-0' : 'opacity-100'"
		/>

		<div v-if="overflowing" class="pointer-events-none absolute inset-x-0 bottom-4 z-10 px-6">
			<div class="relative mx-auto w-full max-w-3xl">
				<div class="absolute bottom-0 right-0">
					<Tooltip :text="jumpLabel" placement="top">
						<Button
							class="pointer-events-auto !bg-surface-elevation-2 shadow-md"
							variant="ghost"
							:icon="pastHalf ? 'lucide-arrow-up' : 'lucide-arrow-down'"
							:aria-label="jumpLabel"
							data-feed-jump
							@click="jump"
						/>
					</Tooltip>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useEventListener, useResizeObserver } from "@vueuse/core";
import { Button, ScrollArea, Tooltip } from "frappe-ui";
import { __ } from "@/i18n";
import type { FeedPages } from "./recordFeeds";
import { useScrollEdges } from "./useScrollEdges";

const props = withDefaults(
	defineProps<{
		paginate?: FeedPages;
		/** The store's error; a page read that sets it stops paging on scroll. */
		error?: unknown;
		/** The first rows are drawn, so the feed may land. */
		ready?: boolean;
		openAtBottom?: boolean;
	}>(),
	{ paginate: undefined, error: undefined, ready: true, openAtBottom: false }
);

const area = ref<InstanceType<typeof ScrollArea> | null>(null);
const scroller = computed(() => area.value?.viewportElement ?? null);
const content = ref<HTMLElement | null>(null);
const { atTop, atBottom, overflowing, pastHalf, measure } = useScrollEdges(scroller);

const landed = ref(!props.openAtBottom);
const stalled = ref(false);
// At the bottom, a row that grows the feed keeps the newest row in view.
let pinned = false;
// The last scroll top seen or set; only a move up from it is the reader leaving the bottom.
let lastTop = 0;
// Distance from the bottom while an older page lands above the reader.
let held: number | null = null;

const jumpLabel = computed(() => (pastHalf.value ? __("Scroll to top") : __("Scroll to bottom")));

onMounted(() => land(props.ready));
watch(() => props.ready, land, { flush: "post" });
watch(() => props.paginate?.isFetchingNextPage, holdFrom, { flush: "pre" });
watch(() => props.paginate?.isFetchingNextPage, holdUntilLanded, { flush: "post" });
watch(
	() => props.error,
	(error) => {
		if (!error) stalled.value = false;
	}
);
useEventListener(scroller, "scroll", onScroll);
useResizeObserver(content, onContentResize);

function land(ready: boolean) {
	if (!ready || landed.value) return;
	toBottom();
	landed.value = true;
	pinned = true;
	pageIfNearTop();
}

// Taken when the read starts, on each scroll during it, and in the pre-flush just before
// its rows are drawn, so the hold keeps where the reader is now.
function holdFrom() {
	const element = scroller.value;
	if (element) held = element.scrollHeight - element.scrollTop;
}

function holdUntilLanded(fetching: boolean | undefined) {
	hold();
	if (fetching) return;
	held = null;
	measure();
}

function onScroll() {
	const top = scroller.value?.scrollTop ?? 0;
	const stays = atBottom.value || (pinned && top >= lastTop);
	pinned = props.openAtBottom && landed.value && stays;
	lastTop = top;
	if (held !== null) holdFrom();
	pageIfNearTop();
}

function onContentResize() {
	if (held !== null) hold();
	else if (pinned) toBottom();
	measure();
	pageIfNearTop();
}

// One screen from the top; a hidden tab has no height and never pages.
function pageIfNearTop() {
	const element = scroller.value;
	const pages = props.paginate;
	if (!element?.clientHeight || !pages || !landed.value || stalled.value) return;
	if (!pages.hasNextPage || pages.isFetchingNextPage) return;
	if (element.scrollTop <= element.clientHeight) void readOlder(pages);
}

// A page can land with no rows and a cursor that moved on, so the next one is read without a scroll.
async function readOlder(pages: FeedPages) {
	const before = props.error;
	await pages.fetchNextPage();
	if (props.error && props.error !== before) stalled.value = true;
	else await nextTick().then(pageIfNearTop);
}

function retry() {
	stalled.value = false;
	if (props.paginate) void readOlder(props.paginate);
}

function hold() {
	const element = scroller.value;
	if (element && held !== null) setTop(element, element.scrollHeight - held);
}

function toBottom() {
	const element = scroller.value;
	if (element) setTop(element, element.scrollHeight);
}

function setTop(element: HTMLElement, top: number) {
	element.scrollTop = top;
	lastTop = element.scrollTop;
}

function jump() {
	const top = pastHalf.value ? 0 : scroller.value?.scrollHeight;
	scroller.value?.scrollTo({ top, behavior: "smooth" });
}
</script>
