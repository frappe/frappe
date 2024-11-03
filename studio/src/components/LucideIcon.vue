<template>
	<component :is="icon" />
</template>

<script setup lang="ts">
import { computed } from "vue"
// NOTE: Find a better way than importing the entire icon library -> increased bundle size
// Timeless icons will replace these most likely
import * as icons from "lucide-vue-next"

const props = defineProps({
	name: {
		type: String,
		required: true,
	},
})

const icon = computed(() => icons[props.name])
</script>
