<script setup lang="ts">
import { ref } from "vue";
import { PhoneInput } from "frappe-ui";

const disabledValue = ref("+91-9876543210");
</script>

<template>
	<div class="flex w-full max-w-sm flex-col gap-4">
		<PhoneInput label="Default" placeholder="98765 43210" />
		<PhoneInput label="Required" required placeholder="98765 43210" />
		<PhoneInput v-model="disabledValue" label="Disabled" disabled />
		<PhoneInput
			label="With error"
			error="This number can't receive OTPs."
			placeholder="98765 43210"
		/>
	</div>
</template>
