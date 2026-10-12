<template>
	<!-- `@container` and `@xl:` come from the app's own Tailwind plugin, not
	from frappe-ui's preset. They compile only if the app's plugins reach the
	island's generated config. -->
	<div class="@container">
		<div class="grid grid-cols-1 gap-2 @xl:grid-cols-3">
			<div class="flex items-center gap-2 rounded bg-surface-gray-2 p-3">
				<LucideChartLine class="h-4 w-4 text-ink-gray-7" />
				<span class="panel-accent text-base text-ink-gray-8">{{ title }}</span>
				<!-- The class comes from a helper module, not from this template. -->
				<span :class="toneClass(count)">{{ count }}</span>
				<Button variant="solid" @click="count++">clicked {{ count }}</Button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { Button } from "frappe-ui";
import LucideChartLine from "~icons/lucide/chart-line";
import { toneClass } from "./tone.js";

defineProps({ title: { type: String, default: "fixture island" } });

const count = ref(0);
</script>
