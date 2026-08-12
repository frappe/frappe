<script setup lang="ts">
import { computed, ref } from "vue";
import { Checkbox, PhoneInput } from "frappe-ui";

const phone = ref("");
const required = ref(true);
const showError = ref(false);

const error = computed(() =>
	showError.value ? "A contact number is required for delivery." : ""
);
</script>

<template>
	<div class="flex items-start gap-8">
		<PhoneInput
			v-model="phone"
			label="Delivery contact"
			description="The courier will call this number on arrival."
			:error="error"
			:required="required"
			placeholder="98765 43210"
			class="w-72"
		/>
		<div class="flex flex-col items-start gap-2 border-l border-outline-gray-2 pl-6">
			<Checkbox v-model="required" label="required" />
			<Checkbox v-model="showError" label="show error" />
		</div>
	</div>
</template>
