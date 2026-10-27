<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Button, Dropdown } from "frappe-ui";
import { NumberCard } from "frappe-ui/charts";
import { load_card, load_trend, open_card } from "./number_card.js";

const props = defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const __ = window.__;
const result = ref(null);
const failed = ref(false);
const trend = ref(null);

async function refresh() {
	failed.value = false;
	try {
		result.value = await load_card(props.widget.number_card_name);
	} catch (e) {
		console.error(e);
		failed.value = true;
		return;
	}
	trend.value = await load_trend(result.value).catch(() => null);
}

onMounted(refresh);
watch(() => props.widget.number_card_name, refresh);

const menu = computed(() => [
	{ label: __("Refresh"), icon: "lucide-refresh-cw", onClick: refresh },
	{ label: __("Open"), icon: "lucide-arrow-up-right", onClick: () => open_card(result.value) },
]);
</script>

<template>
	<NumberCard
		class="group h-full cursor-pointer hover:border-outline-gray-2"
		:title="widget.label"
		:value="result?.value ?? null"
		:color="result?.card.color || undefined"
		:delta="result?.delta"
		delta-suffix="%"
		:delta-format="(value) => frappe.utils.shorten_number(value)"
		:delta-caption="result?.caption || undefined"
		:sparkline="trend ? { data: trend, color: result.card.color || undefined } : undefined"
		:loading="!result && !failed"
		:error="failed ? __('Could not load') : null"
		@click="result && open_card(result)"
	>
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
