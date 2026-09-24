<!-- The Side Panel layout's sections while it loads: PanelSection's 42px header over
     PanelField's label and value grid. -->
<template>
	<div data-panel-sections-skeleton>
		<template v-for="section in 3" :key="section">
			<div class="flex h-[42px] items-center border-t border-outline-gray-1 px-4">
				<Skeleton class="h-4 w-24 rounded-1" />
			</div>
			<div class="flex flex-col gap-2.5 px-4 pb-3 pt-1">
				<div
					v-for="row in 4"
					:key="row"
					class="grid h-[27px] grid-cols-[130px_1fr] items-center gap-2"
				>
					<Skeleton class="h-3 w-20 rounded-1" />
					<Skeleton class="mx-1.5 h-3 w-2/3 rounded-1" />
				</div>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";
</script>
