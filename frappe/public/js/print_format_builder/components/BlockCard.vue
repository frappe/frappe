<template>
	<div class="pfb-block-card">
		<span class="pfb-block-icon" v-html="frappe.utils.icon(icon, 'sm')"></span>
		<div class="pfb-block-info">
			<div class="pfb-block-name">{{ name }}</div>
			<div class="pfb-block-desc text-muted">{{ desc }}</div>
		</div>
		<slot name="action" />
	</div>
</template>

<script setup>
defineProps({
	icon: { type: String, required: true },
	name: { type: String, default: "" },
	desc: { type: String, default: "" },
});
</script>

<style scoped>
.pfb-block-card {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 8px 10px;
	border-radius: var(--radius-md);
	/* the card is drawn by its outline, not by a fill, so the panel stays quiet */
	border: 1px solid var(--outline-gray-2);
	background: var(--fg-color);
	cursor: grab;
	margin: 8px 10px 0;
}

.pfb-block-card:hover {
	background: var(--surface-gray-1);
	border-color: var(--outline-gray-3);
}

.pfb-block-icon {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	border-radius: var(--radius);
	background: var(--surface-gray-2);
	flex-shrink: 0;
}

.pfb-block-info {
	min-width: 0;
	flex: 1;
}

.pfb-block-name {
	font-size: var(--text-sm);
	font-weight: 500;
}

.pfb-block-desc {
	font-size: var(--text-tiny);
	margin-top: 1px;
}
</style>
