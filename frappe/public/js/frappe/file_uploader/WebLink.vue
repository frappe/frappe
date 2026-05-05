<template>
	<div class="file-web-link" :style="{ 'margin-bottom': error_message ? '0' : '0.5rem' }">
		<a href class="text-muted text-medium" @click.prevent="emit('hide-web-link')">
			{{ __("← Back to upload files") }}
		</a>
		<div class="input-group">
			<input
				ref="web_link_input"
				type="text"
				class="form-control mr-1"
				:class="{ 'is-invalid': error_message }"
				:placeholder="__('Attach a web link')"
				v-model="url"
			/>
		</div>
		<div class="text-small text-danger pt-1" v-if="error_message">{{ error_message }}</div>
	</div>
</template>

<script setup>
import { ref, watch } from "vue";

// emits
let emit = defineEmits(["hide-web-link"]);

let url = ref("");
let web_link_input = ref(null);
let error_message = ref("");

watch(url, () => {
	error_message.value = "";
});

function invalid_input(error) {
	error_message.value = error;
	web_link_input.value?.focus();
}

defineExpose({ url, invalid_input });
</script>

<style scoped>
.file-web-link .input-group {
	margin-top: 10px;
}
</style>
