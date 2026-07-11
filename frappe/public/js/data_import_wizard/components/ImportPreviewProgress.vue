<script setup>
import { inject } from "vue";

const preview_loading = inject("preview_loading");
</script>

<template>
	<div
		v-if="preview_loading"
		class="diw-import-preview-progress"
		role="progressbar"
		aria-busy="true"
		aria-valuemin="0"
		aria-valuemax="100"
		:aria-valuetext="__('Loading import file...')"
	>
		<div class="diw-import-preview-progress-track">
			<div class="diw-import-preview-progress-range"></div>
		</div>
	</div>
</template>
