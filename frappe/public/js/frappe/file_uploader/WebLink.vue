<template>
	<div class="file-web-link margin-bottom">
		<a href class="text-muted text-medium" @click.prevent="emit('hide-web-link')">
			{{ __("← Back to upload files") }}
		</a>
		<div class="input-group">
			<input
				type="text"
				class="form-control"
				:placeholder="__('Attach a web link')"
				v-model="url"
			/>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";

// emits
let emit = defineEmits(["hide-web-link"]);

let url = ref("");

defineExpose({ url });
</script>

<style scoped>
.file-web-link .input-group {
	margin-top: 10px;
}
</style>
