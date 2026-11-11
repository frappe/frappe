<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Button, Dropdown } from "frappe-ui";
import { NumberCard } from "frappe-ui/charts";
import { card_is_set_up, load_card, load_trend, open_card } from "./number_card.js";

const props = defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const __ = window.__;
const result = ref(null);
const failed = ref(false);
const trend = ref(null);
const unfinished = computed(
	() => props.widget.record_changed && !card_is_set_up(props.widget.record)
);
let latest = 0;

async function refresh() {
	const run = ++latest;
	failed.value = false;
	if (unfinished.value) return;
	try {
		const loaded = await load_card(
			props.widget.record_changed ? props.widget.record : props.widget.number_card_name
		);
		if (run !== latest) return;
		result.value = loaded;
	} catch (e) {
		if (run !== latest) return;
		console.error(e);
		failed.value = true;
		return;
	}
	const points = await load_trend(result.value).catch(() => null);
	if (run === latest) trend.value = points;
}

onMounted(refresh);
watch(() => props.widget.number_card_name, refresh);
watch(
	() => props.widget.record_changed && JSON.stringify(props.widget.record),
	frappe.utils.debounce((changed) => changed && refresh(), 400)
);

const menu = computed(() => [
	{ label: __("Refresh"), icon: "lucide-refresh-cw", onClick: refresh },
	{ label: __("Open"), icon: "lucide-arrow-up-right", onClick: () => open_card(result.value) },
]);
</script>

<template>
	<NumberCard
		class="group h-full cursor-pointer hover:border-outline-gray-2 dark:border-outline-gray-2 dark:bg-transparent dark:hover:border-outline-gray-3"
		:title="widget.label"
		:value="result?.value ?? null"
		:color="result?.card.color || undefined"
		:delta="result?.delta"
		delta-suffix="%"
		:delta-format="(value) => frappe.utils.shorten_number(value)"
		:delta-caption="result?.caption || undefined"
		:sparkline="trend ? { data: trend, color: result.card.color || undefined } : undefined"
		:loading="!result && !failed && !unfinished"
		:error="failed ? __('Could not load') : null"
		@click="result && open_card(result)"
	>
		<template v-if="unfinished" #empty>
			<p class="text-p-sm text-ink-gray-5">{{ __("Choose what to count") }}</p>
		</template>
		<template #actions>
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
		</template>
	</NumberCard>
</template>
