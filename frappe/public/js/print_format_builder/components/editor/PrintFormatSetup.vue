<template>
	<div class="pfb-setup">
		<div class="pfb-setup-card">
			<div class="pfb-setup-icon" v-html="frappe.utils.icon('file', 'xl')"></div>
			<h3 class="pfb-setup-title">{{ __("How do you want to start?") }}</h3>
			<p class="pfb-setup-subtitle">
				{{ __("Choose a starting point for your print format.") }}
			</p>
			<div class="pfb-setup-options">
				<button class="pfb-setup-option" @click="$emit('start-default')">
					<div
						class="pfb-setup-option-icon"
						v-html="frappe.utils.icon('list', 'md')"
					></div>
					<div class="pfb-setup-option-body">
						<div class="pfb-setup-option-label">{{ __("Start from default") }}</div>
						<div class="pfb-setup-option-desc">
							{{ __("Pre-filled with all document fields. Customize from there.") }}
						</div>
					</div>
					<div
						class="pfb-setup-option-arrow"
						v-html="frappe.utils.icon('chevron-right', 'xs')"
					></div>
				</button>
				<button class="pfb-setup-option" @click="$emit('start-blank')">
					<div
						class="pfb-setup-option-icon"
						v-html="frappe.utils.icon('plus', 'md')"
					></div>
					<div class="pfb-setup-option-body">
						<div class="pfb-setup-option-label">{{ __("Start blank") }}</div>
						<div class="pfb-setup-option-desc">
							{{ __("Empty canvas. Drag and drop fields to build from scratch.") }}
						</div>
					</div>
					<div
						class="pfb-setup-option-arrow"
						v-html="frappe.utils.icon('chevron-right', 'xs')"
					></div>
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
defineEmits(["start-default", "start-blank"]);
</script>

<style scoped>
.pfb-setup {
	display: flex;
	align-items: center;
	justify-content: center;
	min-height: 60vh;
	padding: var(--padding-xl);
}

.pfb-setup-card {
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius-lg);
	padding: var(--padding-xl);
	max-width: 480px;
	width: 100%;
	text-align: center;
	box-shadow: var(--shadow-sm);
}

.pfb-setup-icon {
	color: var(--text-muted);
	margin-bottom: var(--margin-md);
}

.pfb-setup-title {
	font-size: var(--text-lg);
	font-weight: var(--weight-semibold);
	color: var(--text-color);
	margin: 0 0 var(--margin-xs);
}

.pfb-setup-subtitle {
	font-size: var(--text-sm);
	color: var(--text-muted);
	margin: 0 0 var(--margin-lg);
}

.pfb-setup-options {
	display: flex;
	flex-direction: column;
	gap: var(--margin-sm);
	text-align: left;
}

.pfb-setup-option {
	display: flex;
	align-items: center;
	gap: var(--margin-md);
	padding: var(--padding-md);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--fg-color);
	cursor: pointer;
	transition: border-color 0.15s, background 0.15s;
	width: 100%;
	text-align: left;
}

.pfb-setup-option:hover {
	border-color: var(--primary);
	background: var(--blue-50);
}

.pfb-setup-option-icon {
	color: var(--text-muted);
	flex-shrink: 0;
}

.pfb-setup-option:hover .pfb-setup-option-icon {
	color: var(--primary);
}

.pfb-setup-option-body {
	flex: 1;
}

.pfb-setup-option-label {
	font-size: var(--text-sm);
	font-weight: var(--weight-semibold);
	color: var(--text-color);
	margin-bottom: 2px;
}

.pfb-setup-option-desc {
	font-size: var(--text-xs);
	color: var(--text-muted);
}

.pfb-setup-option-arrow {
	color: var(--text-muted);
	flex-shrink: 0;
}
</style>
