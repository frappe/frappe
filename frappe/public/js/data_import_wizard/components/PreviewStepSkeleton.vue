<!-- Preview step loading skeleton — mirrors the table preview layout. -->
<template>
	<div
		class="diw-preview-skeleton diw-wizard-step-skeleton"
		role="status"
		aria-busy="true"
		:aria-label="__('Loading import preview...')"
	>
		<div class="diw-preview-skeleton-toolbar diw-preview-skeleton-toolbar--table">
			<div class="diw-preview-skeleton-actions">
				<div class="diw-preview-skeleton-button" />
			</div>
			<div class="diw-preview-skeleton-meta" />
		</div>
		<div class="diw-preview-skeleton-table-shell">
			<div class="diw-preview-skeleton-table">
				<div class="diw-preview-skeleton-header-row">
					<div class="diw-preview-skeleton-cell diw-preview-skeleton-cell--sm" />
					<div class="diw-preview-skeleton-cell" />
					<div class="diw-preview-skeleton-cell" />
					<div class="diw-preview-skeleton-cell" />
				</div>
				<div v-for="row in body_rows" :key="row" class="diw-preview-skeleton-body-row">
					<div class="diw-preview-skeleton-cell diw-preview-skeleton-cell--sm" />
					<div class="diw-preview-skeleton-cell" />
					<div class="diw-preview-skeleton-cell" />
					<div class="diw-preview-skeleton-cell" />
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
const body_rows = 10;
</script>
