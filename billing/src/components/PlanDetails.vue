<template>
	<ul class="rounded px-7 py-1.5 bg-gray-900 text-white text-base leading-6 list-disc">
		<li class="list-disc">{{ plan.cpu_time_per_day }} compute hours/day</li>
		<li>{{ parseSize(plan.max_database_usage) }} Database</li>
		<li>{{ parseSize(plan.max_storage_usage) }} Disk</li>
		<li>Product Waranty</li>
		<li v-if="plan.support_included">Support Included</li>
		<li v-if="plan.database_access">Database Access</li>
		<li v-if="plan.offsite_backups">Offsite Backups</li>
		<li v-if="plan.private_benches">Private Benches</li>
		<li v-if="plan.monitor_access">Advanced Monitoring</li>
	</ul>
</template>

<script setup>
import { parseSize } from '../utils.js'

const props = defineProps({
	plan: {
		type: Object,
		required: true,
	},
})
</script>
