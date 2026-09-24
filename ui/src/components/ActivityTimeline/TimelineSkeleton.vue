<template>
	<!-- the timeline's own row grid and gutter heights, so the real rows land in place -->
	<div class="flex flex-col gap-2">
		<div
			v-for="(row, i) in shownRows"
			:key="i"
			class="grid w-full grid-cols-[30px_minmax(0,_1fr)] gap-2 px-6 md:px-0"
		>
			<div class="flex justify-center">
				<div v-if="row.kind === 'change'" class="flex h-6 items-center">
					<Skeleton class="size-4 rounded-full" />
				</div>
				<div v-else class="flex h-10 items-center">
					<Skeleton class="size-7 rounded-full" />
				</div>
			</div>
			<div v-if="row.kind === 'change'" class="mb-4 flex h-6 items-center ps-[13px]">
				<Skeleton class="h-3 rounded-1" :class="row.width" />
			</div>
			<div v-else class="mb-4 flex flex-col gap-2">
				<div class="flex h-10 items-center">
					<Skeleton class="h-3 w-1/4 rounded-1" />
				</div>
				<Skeleton v-if="row.kind === 'email'" class="h-3 w-1/3 rounded-1" />
				<Skeleton
					class="w-full rounded-4"
					:class="row.kind === 'email' ? 'h-24' : 'h-16'"
				/>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";
import { computed } from "vue";

const props = defineProps<{
	/** Draws only the first rows; the first two are one-line changes. */
	rows?: number;
}>();

const ROWS: { kind: "change" | "comment" | "email"; width?: string }[] = [
	{ kind: "change", width: "w-2/5" },
	{ kind: "change", width: "w-1/2" },
	{ kind: "comment" },
	{ kind: "change", width: "w-1/3" },
	{ kind: "email" },
	{ kind: "change", width: "w-3/5" },
	{ kind: "comment" },
];

const shownRows = computed(() => ROWS.slice(0, props.rows ?? ROWS.length));
</script>
