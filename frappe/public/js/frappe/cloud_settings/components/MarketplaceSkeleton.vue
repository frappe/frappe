<!--
  Placeholder rows shown while the marketplace catalog loads, mirroring the app
  row layout (logo + title/description + action) so the list doesn't jump.
-->
<template>
	<div class="cloud-settings-apps" aria-hidden="true">
		<div v-for="n in count" :key="n" class="cloud-settings-app">
			<div class="cloud-settings-skeleton cs-skeleton-logo"></div>
			<div class="cloud-settings-app-body">
				<div class="cloud-settings-skeleton cs-skeleton-line" style="width: 45%"></div>
				<div
					class="cloud-settings-skeleton cs-skeleton-line"
					style="width: 80%; margin-top: 8px"
				></div>
			</div>
			<div class="cloud-settings-skeleton cs-skeleton-btn"></div>
		</div>
	</div>
</template>

<script setup>
defineProps({ count: { type: Number, default: 6 } });
</script>
