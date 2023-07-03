<!-- Used as Attach & Attach Image Control -->
<script setup>
const props = defineProps(["df"]);
</script>

<template>
	<div class="control editable">
		<!-- label -->
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>

		<!-- attach button -->
		<button class="btn btn-sm btn-default">{{ __("Attach") }}</button>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>
