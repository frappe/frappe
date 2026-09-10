<script setup lang="ts">
import { ref } from "vue";
import { Phone } from "../index";

const disabledValue = ref("+91-9876543210");
</script>

<template>
	<div class="flex w-full max-w-sm flex-col gap-4">
		<Phone label="Default" placeholder="98765 43210" />
		<Phone label="Required" required placeholder="98765 43210" />
		<Phone v-model="disabledValue" label="Disabled" disabled />
		<Phone
			label="With error"
			error="This number can't receive OTPs."
			placeholder="98765 43210"
		/>
	</div>
</template>
