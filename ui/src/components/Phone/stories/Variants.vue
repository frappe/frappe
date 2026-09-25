<script setup lang="ts">
import { PhoneInput } from "frappe-ui";
</script>

<template>
	<div class="flex w-full max-w-sm flex-col gap-3">
		<PhoneInput variant="subtle" placeholder="Subtle" />
		<PhoneInput variant="outline" placeholder="Outline" />
	</div>
</template>
