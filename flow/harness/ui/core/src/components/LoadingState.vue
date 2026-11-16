<template>
	<!-- the spinner scales with the text it sits in; the host sets size, color and spacing -->
	<div class="flow-late-reveal flex items-center gap-2">
		<Spinner class="h-[1.15em] w-[1.15em]" />
		<slot>Loading…</slot>
	</div>
</template>

<script setup>
import Spinner from "frappe-ui/src/components/Spinner/Spinner.vue"
</script>
