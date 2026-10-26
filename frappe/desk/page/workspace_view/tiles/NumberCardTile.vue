<script setup>
import { computed, onMounted, ref } from "vue";
import { Button, Dropdown, LoadingIndicator } from "frappe-ui";
import { load_card, open_card } from "./number_card.js";

const props = defineProps({
	widget: { type: Object, required: true },
});

const __ = window.__;
const result = ref(null);
const failed = ref(false);

async function refresh() {
	failed.value = false;
	try {
		result.value = await load_card(props.widget.number_card_name);
	} catch (e) {
		console.error(e);
		failed.value = true;
	}
}

onMounted(refresh);

const menu = computed(() => [
	{ label: __("Refresh"), icon: "lucide-refresh-cw", onClick: refresh },
	{ label: __("Open"), icon: "lucide-arrow-up-right", onClick: () => open_card(result.value) },
]);

const delta_icon = computed(() =>
	result.value?.delta > 0 ? "lucide-arrow-up-right" : "lucide-arrow-down-right"
);

const delta_class = computed(() => {
	const delta = result.value?.delta;
	if (!delta) return "text-ink-gray-5";
	return delta > 0 ? "text-ink-green-3" : "text-ink-red-3";
});
</script>

<template>
	<div
		class="group flex h-full cursor-pointer flex-col justify-between rounded-6 border border-outline-gray-1 bg-surface-base p-4 hover:border-outline-gray-2"
		@click="result && open_card(result)"
	>
		<div class="flex items-start justify-between gap-2">
			<div class="truncate text-base text-ink-gray-6">{{ widget.label }}</div>
			<div class="opacity-0 transition-opacity group-hover:opacity-100" @click.stop>
				<Dropdown align="end" :options="menu">
					<template #trigger>
						<Button
							variant="ghost"
							size="sm"
							icon="lucide-more-horizontal"
							:label="__('Number card actions')"
						/>
					</template>
				</Dropdown>
			</div>
		</div>
		<LoadingIndicator v-if="!result && !failed" class="size-4 text-ink-gray-4" />
		<div v-else-if="failed" class="text-base text-ink-gray-5">{{ __("Could not load") }}</div>
		<div v-else class="flex flex-col gap-1">
			<span
				class="text-2xl font-semibold text-ink-gray-9"
				:style="result.card.color ? { color: result.card.color } : null"
			>
				{{ result.value }}
			</span>
			<span
				v-if="result.delta !== null"
				class="flex items-center gap-0.5 text-sm"
				:class="delta_class"
			>
				<span v-if="result.delta" :class="delta_icon" class="size-3" aria-hidden="true" />
				{{ result.delta_label }}% {{ result.caption }}
			</span>
		</div>
	</div>
</template>
