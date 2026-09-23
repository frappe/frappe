<template>
	<div class="pfb-insp-section">
		<div class="pfb-insp-section-head" @click="open = !open">
			<span class="pfb-insp-section-label">{{ label }}</span>
			<div class="d-flex align-items-center" style="gap: 8px">
				<slot name="head" />
				<span
					class="pfb-insp-chevron"
					:class="{ collapsed: !open }"
					v-html="frappe.utils.icon('chevron-down', 'xs')"
				></span>
			</div>
		</div>
		<div v-show="open" :class="padded ? 'pfb-insp-section-body' : ''">
			<slot />
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
	label: { type: String, required: true },
	initOpen: { type: Boolean, default: true },
	padded: { type: Boolean, default: true },
});

const open = ref(props.initOpen);
</script>
