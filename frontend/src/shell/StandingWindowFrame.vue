<!--
  One app's standing window: the docked frame while open, the pill while minimised. The component
  stays mounted in the frame's body whatever the state, so hiding is `v-show`, never `v-if`.
-->
<template>
	<div v-show="entry.state === 'open'" class="pointer-events-auto">
		<FloatingWindow
			mode="docked"
			:minimizable="false"
			role="dialog"
			aria-modal="false"
			:aria-labelledby="titleId"
			class="border border-outline-gray-2 shadow-2xl"
			:style="{ width: `${entry.width}px`, maxHeight: `${maxHeight}px` }"
			:data-standing-window="entry.app"
		>
			<template #header>
				<div class="flex shrink-0 items-center gap-2 px-3 pt-3">
					<span
						v-if="entry.icon"
						class="size-4 shrink-0 text-ink-gray-5"
						:class="entry.icon"
						aria-hidden="true"
					/>
					<Tooltip :text="entry.title">
						<span
							:id="titleId"
							class="min-w-0 truncate text-base font-medium text-ink-gray-8"
							data-standing-title
						>
							{{ entry.title }}
						</span>
					</Tooltip>
					<div class="ml-auto flex shrink-0 items-center">
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

			<div class="p-3">
				<component :is="entry.component" :shell="shell" :window="entry.handle" />
			</div>
		</FloatingWindow>
	</div>

	<div
		v-show="entry.state === 'minimised'"
		class="pointer-events-auto flex h-10 max-w-[400px] cursor-pointer items-center gap-2 rounded-full border border-outline-gray-2 bg-surface-elevation-1 pl-3.5 pr-1.5 shadow-2xl"
		:data-standing-minimised="entry.app"
		@click="restore"
	>
		<span
			v-if="entry.icon"
			class="size-4 shrink-0 text-ink-gray-5"
			:class="entry.icon"
			aria-hidden="true"
		/>
		<Tooltip :text="entry.title">
			<button
				ref="restoreButton"
				type="button"
				class="min-w-0 truncate rounded-2 text-base font-medium text-ink-gray-8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				:aria-label="__('Restore {0}', [entry.title])"
				data-standing-restore
			>
				{{ entry.title }}
			</button>
		</Tooltip>
		<div v-if="entry.actions.length" class="flex shrink-0 items-center" @click.stop>
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
import { nextTick, ref } from "vue";
import { Button, Tooltip } from "frappe-ui";
import { FloatingWindow } from "frappe-ui/experimental";
import { __ } from "@/i18n";
import type { Shell } from "./shellActs";
import type { StandingWindow, StandingWindowAction } from "./standingWindows";

const props = defineProps<{ entry: StandingWindow; shell: Shell; maxHeight: number }>();

const DIVIDER_WIDTH = 280;

const titleId = `standing-window-title-${props.entry.app}`;
const restoreButton = ref<HTMLButtonElement | null>(null);

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
