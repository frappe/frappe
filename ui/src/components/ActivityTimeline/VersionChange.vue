<template>
	<!-- flex-col so the history list stacks under the change line -->
	<span class="inline-flex flex-col gap-1 align-top">
		<span class="inline-flex flex-wrap items-center gap-1.5">
			<!-- diff: prefix + from → to (arrow only when there's a `from`) -->
			<template v-if="change.type === 'diff'">
				<span>{{ change.prefix }}</span>
				<template v-if="change.from != null">
					<span class="font-semibold text-ink-gray-8" :title="full(change.from)">{{
						clip(change.from)
					}}</span>
					<span class="text-ink-gray-5">→</span>
				</template>
				<span class="font-semibold text-ink-gray-8" :title="full(change.to)">{{
					clip(change.to)
				}}</span>
				<!-- chevron reveals the field's change history -->
				<button
					v-if="hasHistory"
					type="button"
					class="text-ink-gray-5 hover:text-ink-gray-7"
					@click="open = !open"
				>
					<FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="size-3.5" />
				</button>
			</template>
			<!-- phrase: finished line -->
			<template v-else>
				<span>{{ change.text }}</span>
			</template>
		</span>

		<!-- change history -->
		<span
			v-if="hasHistory && open && change.type === 'diff'"
			class="flex flex-col gap-0.5 ps-1 text-ink-gray-5"
		>
			<span
				v-for="(hop, idx) in change.history"
				:key="idx"
				class="inline-flex items-center gap-1.5"
			>
				<span class="font-semibold text-ink-gray-7" :title="full(hop.from)">{{
					clip(hop.from)
				}}</span>
				<span>→</span>
				<span class="font-semibold text-ink-gray-7" :title="full(hop.to)">{{
					clip(hop.to)
				}}</span>
			</span>
		</span>
	</span>
</template>

<script setup lang="ts">
import { FeatherIcon } from "frappe-ui";
import { computed, ref } from "vue";
import type { VersionChange } from "./types";

const props = defineProps<{ change: VersionChange }>();

const open = ref(false);
// chevron only when the field churned (>1 hop)
const hasHistory = computed(
	() => props.change.type === "diff" && (props.change.history?.length ?? 0) > 1
);

// clip values for display; show the full value on hover only when clipped
const LIMIT = 40;
const clip = (v?: string) => ((v?.length ?? 0) > LIMIT ? v!.slice(0, LIMIT) + "…" : v ?? "");
const full = (v?: string) => ((v?.length ?? 0) > LIMIT ? v : undefined);
</script>
