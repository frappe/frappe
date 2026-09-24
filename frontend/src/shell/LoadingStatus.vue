<!-- What a screen reader hears for a skeleton, whose bars are hidden from it. One per loading region. -->
<template>
	<span role="status" class="sr-only">{{ __("Loading") }}</span>
</template>

<script setup lang="ts">
import { __ } from "@/i18n";
</script>
