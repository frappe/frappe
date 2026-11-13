<!-- One setting: label and help, then the control in a 320px column on the pane's right edge, so
     stacked rows share both edges. The Customize mark's slot takes no height, so the modes line up. -->
<template>
	<div class="group/row relative isolate py-2" :data-setting="row.key">
		<span data-flash aria-hidden="true" :class="FLASH" />
		<div
			:class="
				wide
					? 'flex flex-col gap-2.5'
					: 'grid grid-cols-[minmax(0,1fr)_320px] items-start gap-x-3'
			"
		>
			<div class="min-w-0 pt-px">
				<p class="flex items-center gap-1 text-base text-ink-gray-8">
					<span class="min-w-0">{{ __(row.label) }}</span>
					<span class="flex h-0 shrink-0 items-center">
						<SettingsMark
							:lock="lock"
							:changed="changed"
							:reset-text="resetText"
							@reset="view.reset(row)"
						/>
					</span>
				</p>
				<p class="mt-0.5 text-p-sm text-ink-gray-5">
					<slot name="help">{{ __(row.help) }}</slot>
				</p>
			</div>
			<div
				class="min-w-0"
				:class="[!wide && 'flex min-h-7 items-center justify-end', lock && 'opacity-60']"
				:inert="Boolean(lock)"
			>
				<slot />
			</div>
		</div>
		<ul v-if="errors.length" class="mt-1.5 text-p-sm text-ink-red-5" data-setting-errors>
			<li v-for="error in errors" :key="error">{{ error }}</li>
		</ul>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { __ } from "@/i18n";
import SettingsMark from "./SettingsMark.vue";
import type { SettingRow } from "./settingsRows";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{ row: SettingRow; wide?: boolean }>();
const view = inject(SettingsViewKey)!;

const FLASH =
	"pointer-events-none absolute -inset-x-3 inset-y-0 -z-10 rounded-4 bg-surface-gray-3 opacity-0";

const lock = computed(() => view.lock(props.row));
const changed = computed(() => !lock.value && view.changed(props.row));
const errors = computed(() => view.errors(props.row));
const resetText = computed(() =>
	__("Reset to {0}'s value ({1})", [view.app, view.shipped(props.row)])
);
</script>
