<template>
	<!-- flex-col so the history list stacks under the change line -->
	<span class="inline-flex flex-col gap-1 align-top">
		<span class="inline-flex flex-wrap items-center gap-1.5 text-ink-gray-5">
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

		<!-- change history nested under the line; single-change row sets :show-history="false" -->
		<VersionChangeHistory
			v-if="hasHistory && open && showHistory && change.type === 'diff'"
			:history="change.history!"
			:author="author"
			:prefix="change.prefix"
		/>
	</span>
</template>

<script setup lang="ts">
import { FeatherIcon } from "frappe-ui";
import { computed } from "vue";
import type { VersionChange } from "./types";
import VersionChangeHistory from "./VersionChangeHistory.vue";

const props = withDefaults(
	defineProps<{ change: VersionChange; showHistory?: boolean; author?: string }>(),
	{ showHistory: true, author: "" }
);

// two-way so the single-change row can drive the chevron while rendering history outside
const open = defineModel<boolean>("open", { default: false });
// chevron only when the field churned (>1 field change)
const hasHistory = computed(
	() => props.change.type === "diff" && (props.change.history?.length ?? 0) > 1
);

// clip values for display; show the full value on hover only when clipped
const LIMIT = 40;
const clip = (v?: string) => ((v?.length ?? 0) > LIMIT ? v!.slice(0, LIMIT) + "…" : v ?? "");
const full = (v?: string) => ((v?.length ?? 0) > LIMIT ? v : undefined);
</script>
