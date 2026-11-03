<!--
  One app's standing window: the docked frame while open, the pill while minimised. The component
  stays mounted in the frame's body whatever the state, so hiding is `v-show`, never `v-if`.
-->
<template>
	<div
		ref="frameEl"
		v-show="entry.state === 'open'"
		class="standing-enter pointer-events-auto min-w-[min(240px,calc(100vw-48px))] shrink-[1000]"
		:class="{ 'fixed max-w-[calc(100vw-48px)]': entry.placed }"
		:style="{ width: `${entry.width}px`, ...frameAt }"
	>
		<FloatingWindow
			mode="docked"
			:minimizable="false"
			role="dialog"
			aria-modal="false"
			:aria-labelledby="titleId"
			class="w-full border border-outline-gray-2 shadow-2xl"
			:style="{ maxHeight: `${frameMaxHeight}px` }"
			:data-standing-window="entry.app"
		>
			<template #header>
				<div
					class="flex shrink-0 cursor-move touch-none items-center gap-2 px-4 pt-4"
					data-standing-header
					@pointerdown="drag.start($event, frameEl!, frameWidth)"
					@dblclick="drag.putBack"
				>
					<span
						v-if="entry.icon"
						class="size-4 shrink-0 text-ink-gray-5"
						:class="entry.icon"
						aria-hidden="true"
					/>
					<Tooltip :text="entry.title" :disabled="!titleTruncated">
						<span
							:id="titleId"
							ref="titleEl"
							class="min-w-0 truncate text-base font-medium text-ink-gray-8"
							data-standing-title
						>
							{{ entry.title }}
						</span>
					</Tooltip>
					<div
						class="ml-auto flex shrink-0 cursor-default items-center"
						@pointerdown.stop
						@dblclick.stop
					>
						<Button
							v-for="(action, index) in entry.actions"
							:key="index"
							:icon="action.icon"
							variant="ghost"
							:theme="action.theme ?? 'gray'"
							:label="action.label"
							:tooltip="action.label"
							data-standing-action
							@click="run(action)"
						/>
						<span
							v-if="entry.actions.length && entry.width >= DIVIDER_WIDTH"
							class="mx-1 h-4 border-l border-outline-gray-2"
							aria-hidden="true"
							data-standing-divider
						/>
						<Button
							icon="lucide-minus"
							variant="ghost"
							:label="__('Minimise')"
							:tooltip="__('Minimise')"
							data-standing-minimise
							@click="minimise"
						/>
						<Button
							v-if="entry.closable"
							icon="lucide-x"
							variant="ghost"
							:label="__('Close')"
							:tooltip="__('Close')"
							data-standing-close
							@click="entry.handle.close()"
						/>
					</div>
				</div>
			</template>

			<div class="p-4">
				<component :is="entry.component" :shell="shell" :window="entry.handle" />
			</div>
		</FloatingWindow>
	</div>

	<div
		v-show="entry.state === 'minimised'"
		ref="pill"
		class="standing-enter pointer-events-auto flex h-10 min-w-0 max-w-[400px] cursor-pointer touch-none select-none items-center gap-2 rounded-full border border-outline-gray-2 bg-surface-elevation-1 pl-3.5 shadow-2xl"
		:class="[
			entry.actions.length ? 'pr-1.5' : 'pr-3.5',
			{ 'standing-attention': entry.attention, fixed: entry.placed },
		]"
		:style="{ minWidth: `min(${pillWidth}px, calc(100vw - 48px))`, ...pillAt }"
		:data-standing-minimised="entry.app"
		@pointerdown="drag.start($event, pill!)"
		@click="restore"
	>
		<span
			v-if="entry.icon"
			class="size-4 shrink-0 text-ink-gray-5"
			:class="entry.icon"
			aria-hidden="true"
		/>
		<button
			ref="restoreButton"
			type="button"
			class="min-w-0 truncate rounded-2 text-base font-medium text-ink-gray-8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
			:aria-label="__('Restore {0}', [entry.title])"
			data-standing-restore
		>
			{{ entry.title }}
		</button>
		<div
			v-if="entry.actions.length"
			class="flex shrink-0 items-center"
			@pointerdown.stop
			@click.stop
		>
			<Button
				v-for="(action, index) in entry.actions"
				:key="index"
				:icon="action.icon"
				variant="ghost"
				:theme="action.theme ?? 'gray'"
				:label="action.label"
				:tooltip="action.label"
				data-standing-action
				@click="run(action)"
			/>
		</div>
	</div>

	<span class="sr-only" aria-live="polite">{{ entry.state === "open" ? entry.title : "" }}</span>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useElementBounding, useResizeObserver, useWindowSize } from "@vueuse/core";
import { Button, Tooltip } from "frappe-ui";
import { FloatingWindow } from "frappe-ui/experimental";
import { __ } from "@/i18n";
import type { Shell } from "./shellActs";
import type { StandingWindow, StandingWindowAction } from "./standingWindows";
import { clampPlacement, MARGIN, useWindowDrag } from "./windowDrag";

const props = defineProps<{ entry: StandingWindow; shell: Shell; maxHeight: number }>();

const DIVIDER_WIDTH = 280;

const titleId = `standing-window-title-${props.entry.app}`;
const restoreButton = ref<HTMLButtonElement | null>(null);

const titleEl = ref<HTMLElement | null>(null);
const titleTruncated = ref(false);
const measureTitle = () => {
	titleTruncated.value =
		!!titleEl.value && titleEl.value.scrollWidth > titleEl.value.clientWidth;
};
useResizeObserver(titleEl, measureTitle);
watch(() => props.entry.title, measureTitle, { flush: "post" });

// A ticking title ("Alice · 00:42") changes width by a pixel as digits change, so the pill only grows.
const pill = ref<HTMLElement | null>(null);
const pillWidth = ref(0);
useResizeObserver(pill, ([entry]) => {
	pillWidth.value = Math.max(pillWidth.value, entry.borderBoxSize?.[0]?.inlineSize ?? 0);
});

const drag = useWindowDrag(props.entry);
const frameEl = ref<HTMLElement | null>(null);
const pillSize = useElementBounding(pill);
const viewport = useWindowSize();

// The least room kept above a placed window, so its pill opens a frame with a header and some body.
const PILL_HEIGHT = 40;
const FRAME_HEIGHT = 160;

const frameWidth = computed(() => Math.min(props.entry.width, viewport.width.value - 2 * MARGIN));

function clampedPlacement(width: number, minHeight: number) {
	const { placed } = props.entry;
	if (!placed) return undefined;
	const viewportBox = { width: viewport.width.value, height: viewport.height.value };
	const { left, bottom } = clampPlacement(placed, viewportBox, width, minHeight);
	return { left: `${left}px`, bottom: `${bottom}px` };
}
const frameAt = computed(() => clampedPlacement(frameWidth.value, FRAME_HEIGHT));
const pillAt = computed(() => clampedPlacement(pillSize.width.value, PILL_HEIGHT));
const frameMaxHeight = computed(() =>
	frameAt.value
		? viewport.height.value - parseFloat(frameAt.value.bottom) - MARGIN
		: props.maxHeight
);

// Focus follows only the user's own click; the app's open() and minimise() never move it.
async function minimise() {
	props.entry.handle.minimise();
	await nextTick();
	restoreButton.value?.focus();
}

async function restore() {
	props.entry.handle.open();
	await nextTick();
	document
		.querySelector<HTMLElement>(
			`[data-standing-window="${props.entry.app}"] [data-standing-minimise]`
		)
		?.focus();
}

async function run(action: StandingWindowAction) {
	try {
		await action.run();
	} catch (error) {
		console.error(
			`[frappe] ${props.entry.app}'s window action "${action.label}" failed.`,
			error
		);
	}
}
</script>

<style scoped>
/* v-show's display none→shown restarts the animation: keep v-show, with no leave transition. */
@media (prefers-reduced-motion: no-preference) {
	.standing-enter {
		transform-origin: bottom right;
		animation: standing-enter 150ms ease-out;
	}
	.standing-attention {
		animation-name: standing-enter, standing-attention;
		animation-duration: 150ms, 1.6s;
		animation-iteration-count: 1, infinite;
	}
}
/* Reduced motion keeps the cue as a steady ring. */
.standing-attention {
	box-shadow: 0 0 0 3px var(--outline-gray-3), var(--tw-shadow);
}
@keyframes standing-enter {
	from {
		opacity: 0;
		transform: scale(0.98);
	}
}
@keyframes standing-attention {
	from {
		box-shadow: 0 0 0 0 var(--outline-gray-3), var(--tw-shadow);
	}
	to {
		box-shadow: 0 0 0 10px transparent, var(--tw-shadow);
	}
}
</style>
