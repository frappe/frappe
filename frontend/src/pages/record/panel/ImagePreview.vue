<!-- The picture of an Image row at full size. -->
<template>
	<Dialog v-model:open="open" :title="title" size="3xl">
		<img :src="url" :alt="title" class="mx-auto max-h-[70vh] max-w-full object-contain" />
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog } from "frappe-ui";

defineProps<{ url: string; title: string }>();
const open = defineModel<boolean>("open", { required: true });
</script>
