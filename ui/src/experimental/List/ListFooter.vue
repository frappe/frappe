<!-- The list footer: page-size tabs, Load More, and "N of M". The host sets its padding.
     A capped total is a button; its click asks the host for the exact number. -->
<template>
	<div
		class="flex shrink-0 items-center justify-between gap-2 border-t border-outline-gray-1 py-2"
	>
		<div class="flex items-center gap-2">
			<TabButtons :modelValue="pageSize" :options="tabs" />
			<Button
				v-if="hasNextPage ?? (hasCounts && rowCount < totalCount)"
				variant="subtle"
				label="Load More"
				@click="emit('load-more')"
			/>
		</div>
		<div class="flex items-center gap-2">
			<span v-if="hasCounts" class="text-sm text-ink-gray-5">
				{{ rowCount }} of
				<template v-if="totalUnknown">many</template>
				<button
					v-else-if="totalCapped"
					type="button"
					class="underline-offset-2 hover:underline"
					@click="emit('count')"
				>
					{{ totalCount }}+
				</button>
				<template v-else>{{ totalCount }}</template>
			</span>
			<Skeleton v-else class="h-3 w-16 rounded-1" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, Skeleton, TabButtons } from "frappe-ui";
import { computed } from "vue";

const props = withDefaults(
	defineProps<{
		rowCount?: number;
		totalCount?: number;
		/** False until the first answer lands, which shows a placeholder instead of "0 of 0". */
		hasCounts?: boolean;
		/** The total is a floor, shown with a trailing "+". */
		totalCapped?: boolean;
		/** The server gave up counting; the total reads "many". */
		totalUnknown?: boolean;
		/** Whether Load More shows; unset, the counts decide. */
		hasNextPage?: boolean;
		pageSizeOptions?: number[];
	}>(),
	{
		rowCount: 0,
		totalCount: 0,
		hasCounts: false,
		totalCapped: false,
		totalUnknown: false,
		// An explicit default keeps an absent prop undefined; Vue would cast it to false otherwise.
		hasNextPage: undefined,
		pageSizeOptions: () => [20, 100, 500, 2500],
	}
);

const pageSize = defineModel<number>("pageSize", { default: 20 });

const emit = defineEmits<{
	"load-more": [];
	"page-size": [size: number];
	/** The capped total was clicked. */
	count: [];
}>();

// Each tab's own click, not the model: a click on the chosen size is still a choice, and
// after a Load More it means "back to this many"; a restored value emits nothing.
const tabs = computed(() =>
	props.pageSizeOptions.map((size) => ({
		label: String(size),
		value: size,
		onClick: () => choosePageSize(size),
	}))
);

function choosePageSize(size: number) {
	pageSize.value = size;
	emit("page-size", size);
}
</script>
