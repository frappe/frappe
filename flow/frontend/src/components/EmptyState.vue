<script setup>
import BrandMark from "./BrandMark.vue";
import { __ } from "@/lib/translate";

defineProps({
	setup: { type: Boolean, default: false },
	hasModels: { type: Boolean, default: true },
	hasAgents: { type: Boolean, default: true },
});
</script>

<template>
	<div
		class="flex flex-1 flex-col items-center justify-center gap-2.5 text-center text-ink-gray-6"
	>
		<BrandMark :size="34" />

		<template v-if="setup">
			<div class="text-lg font-semibold text-ink-gray-9">
				{{ __("Finish setup to start") }}
			</div>
			<div class="max-w-[260px] text-xs leading-relaxed">
				{{ __("The assistant needs a few things configured first:") }}
			</div>
			<ol class="mt-1 flex max-w-[280px] flex-col gap-2 text-left">
				<li
					v-if="!hasModels"
					class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-xs leading-relaxed text-ink-gray-8"
				>
					{{ __("Create and enable a Flow Model with your provider credentials.") }}
				</li>
				<li
					v-if="!hasAgents"
					class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-xs leading-relaxed text-ink-gray-8"
				>
					{{
						__(
							"Enable a Flow Agent (Flow Agent is created automatically once a model exists)."
						)
					}}
				</li>
				<li
					class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-xs leading-relaxed text-ink-gray-8"
				>
					{{
						__(
							"Enable Server Scripts in your site config so the assistant can run code."
						)
					}}
				</li>
			</ol>
		</template>

		<template v-else>
			<div class="text-lg font-semibold text-ink-gray-9">{{ __("Flow") }}</div>
			<div class="max-w-[240px] text-xs leading-relaxed">
				{{ __("Ask about your data, draft records, or run a task.") }}
			</div>
		</template>
	</div>
</template>
