<script setup lang="ts">
import { Phone } from "../index";
</script>

<template>
	<div class="flex w-full max-w-sm flex-col gap-3">
		<Phone size="sm" placeholder="Small" />
		<Phone size="md" placeholder="Medium" />
		<Phone size="lg" placeholder="Large" />
	</div>
</template>
