<!-- Fix Issues loading skeleton — self-contained layout matching the mounted step. -->
<template>
	<div
		class="diw-fix-issues-skeleton-root"
		role="status"
		aria-busy="true"
		:aria-label="__('Checking import file for issues...')"
	>
		<section class="diw-fis-section">
			<div class="diw-fis-section-head diw-skeleton-shimmer" />
			<div class="diw-fis-group-label diw-skeleton-shimmer" />
			<div v-for="row in warning_rows" :key="`warning-${row}`" class="diw-fis-warning">
				<div class="diw-fis-warning-accent diw-skeleton-shimmer" aria-hidden="true" />
				<div class="diw-fis-warning-content">
					<div class="diw-fis-warning-title diw-skeleton-shimmer" />
					<div class="diw-fis-warning-line diw-skeleton-shimmer" />
					<div
						class="diw-fis-warning-line diw-skeleton-shimmer diw-fis-warning-line--short"
					/>
				</div>
			</div>
		</section>

		<section class="diw-fis-section">
			<div class="diw-fis-section-head diw-fis-section-head--sm diw-skeleton-shimmer" />
			<div class="diw-fis-grid">
				<div class="diw-fis-grid-header">
					<div class="diw-fis-grid-cell diw-fis-grid-cell--no diw-skeleton-shimmer" />
					<div class="diw-fis-grid-cell diw-skeleton-shimmer" />
					<div class="diw-fis-grid-cell diw-skeleton-shimmer" />
					<div class="diw-fis-grid-cell diw-fis-grid-cell--count diw-skeleton-shimmer" />
					<div class="diw-fis-grid-cell diw-fis-grid-cell--map diw-skeleton-shimmer" />
					<div
						class="diw-fis-grid-cell diw-fis-grid-cell--action diw-skeleton-shimmer"
					/>
				</div>
				<div v-for="row in grid_rows" :key="`grid-${row}`" class="diw-fis-grid-row">
					<div class="diw-fis-grid-cell diw-fis-grid-cell--no diw-skeleton-shimmer" />
					<div class="diw-fis-grid-cell diw-skeleton-shimmer" />
					<div class="diw-fis-grid-cell diw-skeleton-shimmer" />
					<div class="diw-fis-grid-cell diw-fis-grid-cell--count diw-skeleton-shimmer" />
					<div class="diw-fis-grid-cell diw-fis-grid-cell--map diw-skeleton-shimmer" />
					<div
						class="diw-fis-grid-cell diw-fis-grid-cell--action diw-skeleton-shimmer"
					/>
				</div>
			</div>
		</section>
	</div>
</template>

<script setup>
const warning_rows = 3;
const grid_rows = 5;
</script>
