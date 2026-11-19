<!-- A link to a record: a plain click asks the host to open it, any other click is the browser's. -->
<template>
	<a :href="href" @click="onClick"><slot /></a>
</template>

<script setup lang="ts">
defineProps<{ href: string }>();
const emit = defineEmits<{ open: [] }>();

// It sits inside a control whose own click opens an editor or a row.
function onClick(event: MouseEvent) {
	event.stopPropagation();
	if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
		return;
	event.preventDefault();
	emit("open");
}
</script>
