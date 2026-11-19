<!-- An app's or a module's address that lands nowhere: nothing in it the person can open. -->
<template>
	<PageFrame :state="{ name: 'nothingToOpen' }" />
</template>

<script setup lang="ts">
import PageFrame from "./PageFrame.vue";
</script>
