<template>
	<div ref="rootEl" class="flex h-full py-20" :class="side === 'start' ? 'pe-20' : 'ps-20'">
		<div class="relative flex min-h-0 flex-1">
			<div
				v-for="layer in LAYERS"
				:key="layer.end"
				aria-hidden="true"
				data-slot="setup-preview-layer"
				class="setup-preview-open absolute h-full border border-outline-gray-2 bg-surface-gray-2 transition-opacity duration-300 motion-reduce:transition-none"
				:class="[side === 'start' ? layer.start : layer.end, expanded && 'opacity-0']"
			/>
			<div
				ref="windowEl"
				inert
				aria-hidden="true"
				data-slot="setup-preview-window"
				class="setup-preview-open relative min-h-0 flex-1 overflow-hidden border border-outline-gray-2 bg-surface-base shadow-2xl"
				:class="side === 'start' ? 'rounded-e-8 border-s-0' : 'rounded-s-8 border-e-0'"
				:style="expandStyle"
				@transitionend.self="settle"
			>
				<div
					data-slot="setup-preview-drawing"
					class="absolute top-0 flex flex-col"
					:class="side === 'start' ? 'end-0' : 'start-0'"
					:style="drawingStyle"
				>
					<div
						v-if="url"
						data-slot="setup-preview-browser"
						class="grid shrink-0 transition-[grid-template-rows] duration-[600ms] ease-[cubic-bezier(0.33,1,0.68,1)] motion-reduce:transition-none"
						:class="expanded ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]'"
					>
						<div class="min-h-0 overflow-hidden">
							<div class="relative flex h-11 items-end gap-1 bg-surface-gray-2 px-3">
								<span
									v-if="activeTabStart !== null"
									class="absolute bottom-0 h-9 w-[240px] rounded-t-[10px] bg-surface-base transition-[inset-inline-start] duration-500 ease-[cubic-bezier(.22,1,.36,1)] motion-reduce:transition-none"
									:style="{ insetInlineStart: activeTabStart + 'px' }"
								/>
								<div class="flex h-full items-center gap-2 pe-4 ps-1">
									<span
										v-for="light in TRAFFIC_LIGHTS"
										:key="light"
										class="size-3 rounded-full border border-black/10"
										:class="light"
									/>
								</div>
								<div
									v-for="(tab, index) in tabs"
									:key="index"
									:data-tab-index="index"
									class="relative flex h-9 w-[240px] items-center gap-2 px-3"
								>
									<span
										class="flex size-4 shrink-0 overflow-hidden rounded-[4px]"
									>
										<slot name="tab-icon" :tab="tab" />
									</span>
									<Transition v-bind="FADE">
										<span
											:key="tab.key ?? tab.title"
											class="min-w-0 flex-1 truncate text-sm transition-colors duration-500"
											:class="
												tab.active ? 'text-ink-gray-8' : 'text-ink-gray-5'
											"
										>
											{{ tab.title }}
										</span>
									</Transition>
									<span
										class="lucide-x size-3.5 text-ink-gray-5 transition-opacity duration-500"
										:class="tab.active ? 'opacity-100' : 'opacity-0'"
									/>
								</div>
								<span
									class="lucide-plus mb-2.5 ms-1 size-4 self-end text-ink-gray-6"
								/>
							</div>
							<div
								class="flex h-11 items-center gap-4 border-b border-outline-gray-1 bg-surface-base px-4"
							>
								<span
									class="lucide-arrow-left size-4 text-ink-gray-4 rtl:rotate-180"
								/>
								<span
									class="lucide-arrow-right size-4 text-ink-gray-4 rtl:rotate-180"
								/>
								<span class="lucide-rotate-cw size-4 text-ink-gray-4" />
								<div
									class="flex h-7 min-w-0 flex-1 items-center gap-2 rounded-full bg-surface-gray-2 px-3"
								>
									<span class="lucide-lock size-3.5 shrink-0 text-ink-gray-5" />
									<Transition v-bind="FADE">
										<span :key="url" class="truncate text-sm text-ink-gray-7">
											{{ url }}
										</span>
									</Transition>
									<span
										class="lucide-star ms-auto size-3.5 shrink-0 text-ink-gray-5"
									/>
								</div>
								<template v-if="user">
									<Avatar :label="user.name" :image="user.image" size="sm" />
									<span
										class="lucide-ellipsis-vertical size-4 text-ink-gray-5"
									/>
								</template>
							</div>
						</div>
					</div>
					<div
						ref="appEl"
						data-slot="setup-preview-app"
						class="relative min-h-0 flex-1 overflow-hidden"
						:style="{
							'--setup-preview-visible': visibleWidth + 'px',
							'--setup-preview-hidden': hiddenWidth + 'px',
						}"
					>
						<slot />
					</div>
					<SetupPreviewCursor
						v-if="cursor && placed && !reducedMotion"
						ref="cursorRef"
						:x="cursorPoint.x"
						:y="cursorPoint.y + appTop"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { useElementSize, usePreferredReducedMotion } from "@vueuse/core";
import { Avatar } from "frappe-ui";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import type { CSSProperties } from "vue";
import SetupPreviewCursor from "./SetupPreviewCursor.vue";

export interface SetupPreviewTab {
	title: string;
	active?: boolean;
	key?: string;
}

/** A spot in the app's own pixels, from its top left corner below the browser bar. */
export interface SetupPreviewPoint {
	x: number;
	y: number;
}

const props = withDefaults(
	defineProps<{
		/** The screen edge the window sits flush against. Pass the `side` of SetupFlow's `#preview` slot. */
		side?: "start" | "end";
		/** True grows the window over the whole screen, so the setup hands over to the app it previews. */
		expanded?: boolean;
		/**
		 * The width the app is laid out at, in pixels. The window and its browser bar are drawn
		 * a little larger than the space on screen, so the app's far side runs off the edge.
		 */
		appWidth?: number;
		/** The address shown in a browser bar above the app. Unset, there is no bar. */
		url?: string;
		/**
		 * The browser's tabs; the one marked active is the app's. A title fades in when it
		 * changes; give the tab a `key` to change it in place, such as a name being typed.
		 */
		tabs?: SetupPreviewTab[];
		/** The signed-in person, shown at the end of the address bar. */
		user?: { name: string; image?: string | null };
		/**
		 * Where a pointer rests in the app: a point, or a CSS selector of an element in the
		 * app, which it points at the middle of. Hidden for people who reduce motion.
		 */
		cursor?: SetupPreviewPoint | string | null;
	}>(),
	{
		side: "end",
		expanded: false,
		appWidth: 1120,
		url: undefined,
		tabs: () => [],
		user: undefined,
		cursor: null,
	}
);

const emit = defineEmits<{
	/** The window covers the screen: the host can navigate to the app now. */
	expanded: [];
}>();

defineSlots<{
	/** The app as it is being set up, built from the app's own components. */
	default?: () => unknown;
	/** The icon of a tab in the browser bar, such as the app's logo. */
	"tab-icon"?: (props: { tab: SetupPreviewTab }) => unknown;
}>();

const TRAFFIC_LIGHTS = ["bg-[#ff5f57]", "bg-[#febc2e]", "bg-[#28c840]"];
// Two windows stacked behind, so the preview reads as one of several the owner has open.
// By side: `end` sits the window against the end edge, `start` against the start edge.
const LAYERS = [
	{
		end: "-top-6 start-10 end-0 rounded-s-8 border-e-0 opacity-60",
		start: "-top-6 start-0 end-10 rounded-e-8 border-s-0 opacity-60",
	},
	{
		end: "-top-3 start-5 end-0 rounded-s-8 border-e-0",
		start: "-top-3 start-0 end-5 rounded-e-8 border-s-0",
	},
];
const FADE = {
	mode: "out-in" as const,
	enterActiveClass: "transition duration-300 ease-out motion-reduce:transition-none",
	enterFromClass: "opacity-0",
	leaveActiveClass: "transition duration-150 motion-reduce:transition-none",
	leaveToClass: "opacity-0",
};

const EXPAND = "600ms cubic-bezier(0.33, 1, 0.68, 1)";
const rootEl = ref<HTMLElement | null>(null);
const windowEl = ref<HTMLElement | null>(null);
const appEl = ref<HTMLElement | null>(null);
const expandStyle = ref<CSSProperties>({});

const { width: rootWidth } = useElementSize(rootEl);
const { width: windowWidth, height: windowHeight } = useElementSize(windowEl);
// The scale the previews were tuned at; once handed over, the app is shown at its real size.
const scale = computed(() =>
	props.expanded ? 1 : Math.min(1.15, (rootWidth.value * 0.92) / 0.75 / props.appWidth) || 0.9
);
/** How much of the app is on screen, in the app's own pixels. */
const visibleWidth = computed(() => Math.round(windowWidth.value / scale.value));
/** How much of the app runs off the start of the window: on the `start` side the end part shows. */
const hiddenWidth = computed(() =>
	props.side === "start" && !props.expanded
		? Math.max(0, props.appWidth - visibleWidth.value)
		: 0
);
const drawingStyle = computed<CSSProperties>(() => {
	const rtl = document.documentElement.dir === "rtl";
	const fromEnd = (props.side === "start") !== rtl;
	return {
		width: `${props.expanded ? visibleWidth.value : props.appWidth}px`,
		height: `${windowHeight.value / scale.value}px`,
		transform: `scale(${scale.value})`,
		transformOrigin: fromEnd ? "top right" : "top left",
		transition: props.expanded ? `transform ${EXPAND}` : undefined,
	};
});

// The active tab's background slides between tabs, as a browser's does.
const activeTabStart = ref<number | null>(null);
async function placeActiveTab() {
	await nextTick();
	const index = props.tabs.findIndex((t) => t.active);
	const tab = windowEl.value?.querySelector<HTMLElement>(`[data-tab-index="${index}"]`);
	const row = tab?.parentElement;
	if (!tab || !row) return (activeTabStart.value = null);
	const rtl = document.documentElement.dir === "rtl";
	activeTabStart.value = rtl
		? row.offsetWidth - tab.offsetLeft - tab.offsetWidth
		: tab.offsetLeft;
}
watch(() => [props.url, ...props.tabs.map((t) => t.active)], placeActiveTab);
onMounted(placeActiveTab);

const motion = usePreferredReducedMotion();
const reducedMotion = computed(() => motion.value === "reduce");
const cursorRef = ref<InstanceType<typeof SetupPreviewCursor> | null>(null);
const cursorPoint = reactive<SetupPreviewPoint>({ x: 0, y: 0 });
const appTop = ref(0);
// Shown once it has a spot, so it does not slide in from the window's corner.
const placed = ref(false);
let measureLater: ReturnType<typeof setTimeout> | undefined;

function pointAtSelector(selector: string): SetupPreviewPoint | null {
	const el = appEl.value?.querySelector(selector);
	if (!el || !appEl.value) return null;
	const app = appEl.value.getBoundingClientRect();
	const box = el.getBoundingClientRect();
	const drawn = app.width / appEl.value.offsetWidth || 1;
	return {
		x: (box.left + box.width / 2 - app.left) / drawn,
		y: (box.top + box.height / 2 - app.top) / drawn,
	};
}

function placeCursor() {
	appTop.value = appEl.value?.offsetTop ?? 0;
	const point = typeof props.cursor === "string" ? pointAtSelector(props.cursor) : props.cursor;
	if (!point) return;
	Object.assign(cursorPoint, point);
	placed.value = true;
}

watch(
	() => props.cursor,
	async (cursor) => {
		if (cursor && typeof cursor !== "string") placeCursor();
		await nextTick();
		placeCursor();
		// A page sliding in moves the element after it renders; point at where it lands.
		clearTimeout(measureLater);
		measureLater = setTimeout(placeCursor, 650);
	},
	{ immediate: true }
);
watch(
	() => props.url,
	() => nextTick(placeCursor)
);
// A resized window moves what a selector points at, such as the centred sign-in button.
watch([visibleWidth, windowHeight], () => {
	if (typeof props.cursor === "string") placeCursor();
});

/** Presses where the cursor rests, for a host moving the app on to another page. */
function click() {
	cursorRef.value?.click();
}
defineExpose({ click });

let settled = false;
let fallback: ReturnType<typeof setTimeout> | undefined;

function settle() {
	if (settled || !props.expanded) return;
	settled = true;
	clearTimeout(fallback);
	emit("expanded");
}

watch(
	() => props.expanded,
	async (expanded) => {
		if (!expanded || !windowEl.value) return;
		const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
		const { top, left, width, height } = windowEl.value.getBoundingClientRect();
		// Fixed at its current place first, then grown to the screen, so the move animates.
		expandStyle.value = {
			position: "fixed",
			zIndex: 50,
			top: `${top}px`,
			left: `${left}px`,
			width: `${width}px`,
			height: `${height}px`,
		};
		if (reduced) return settle();
		await nextTick();
		// Lay out the starting place before the end one is set, or the browser skips the move.
		windowEl.value?.getBoundingClientRect();
		requestAnimationFrame(() => {
			expandStyle.value = {
				...expandStyle.value,
				top: "0px",
				left: "0px",
				width: "100vw",
				height: "100vh",
				borderRadius: "0px",
				transition: ["top", "left", "width", "height", "border-radius"]
					.map((property) => `${property} ${EXPAND}`)
					.join(", "),
			};
		});
		// A background tab can skip transitionend; the hand-over must still happen.
		fallback = setTimeout(settle, 800);
	}
);

onBeforeUnmount(() => {
	clearTimeout(fallback);
	clearTimeout(measureLater);
});
</script>

<style scoped>
@media (prefers-reduced-motion: no-preference) {
	.setup-preview-open {
		animation: setup-preview-open 400ms cubic-bezier(0.16, 1, 0.3, 1) backwards;
	}
}

@keyframes setup-preview-open {
	from {
		opacity: 0;
		transform: scale(0.98);
	}
}
</style>
