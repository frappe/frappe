<!--
  BillingProfileCard — inline "Add billing details" flow. These go on every invoice
  and must exist before a payment method can be added. Currency is chosen first and
  then locked (it denominates the wallet and invoices). Required fields mirror
  Central's billing-profile validation; Save stays disabled until they're filled.
-->
<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import SelectMenu from "./SelectMenu.vue";

const emit = defineEmits(["close", "saved"]);
const store = inject("store");

// Required fields mirror Central's _REQUIRED_PROFILE_FIELDS (currency + legal
// identity + address). Email and GSTIN are optional (GSTIN is validated on save).
const REQUIRED = ["currency", "legal_name", "address_line1", "city", "state", "country", "pincode"];

const form = reactive({
	currency: "", legal_name: "", email: "", address_line1: "",
	city: "", state: "", country: "", pincode: "", gstin: "",
});
const currencyOptions = ref([]);
const loaded = ref(false);
const working = ref(false);
const error = ref("");

onMounted(load);

const canSave = computed(() => !working.value && REQUIRED.every((key) => form[key].trim()));

async function load() {
	error.value = "";
	try {
		const profile = await store.api.getBillingProfile();
		currencyOptions.value = profile.supported_currencies || [];
		for (const key of Object.keys(form)) form[key] = profile[key] || "";
		loaded.value = true;
	} catch (exception) {
		error.value = store.api.getErrorMessage(exception);
	}
}

async function save() {
	if (!canSave.value) return;
	working.value = true;
	error.value = "";
	try {
		await store.api.saveBillingProfile({ ...form });
		await store.loadBilling(true);
		emit("saved");
	} catch (exception) {
		error.value = store.api.getErrorMessage(exception);
	} finally {
		working.value = false;
	}
}
</script>

<template>
	<div class="cloud-settings-card cloud-settings-stack">
		<div>
			<div class="cloud-settings-title-lg" style="font-size: var(--text-base)">
				{{ __("Add billing details") }}
			</div>
			<p class="cloud-settings-sub">
				{{ __("These go on every invoice - we'll need them before adding a payment method.") }}
			</p>
		</div>

		<div v-if="error" class="cloud-settings-alert error">
			<svg class="icon icon-sm"><use href="#icon-triangle-alert"></use></svg>
			<span>{{ error }}</span>
		</div>

		<div v-if="!loaded" class="cloud-settings-state" style="min-height: 80px">{{ __("Loading") }}</div>
		<template v-else>
			<div class="cloud-settings-form">

				<div class="cloud-settings-form-grid">
				<div class="cloud-settings-field">
					<label>{{ __("Legal name") }} <span class="cloud-settings-req">*</span></label>
					<input v-model="form.legal_name" class="cloud-settings-input" :disabled="working" />
				</div>

				<div class="cloud-settings-field">
					<label>{{ __("Billing email") }}</label>
					<input v-model="form.email" type="email" class="cloud-settings-input"
						placeholder="billing@company.com" :disabled="working" />
				</div>
			</div>

				<div class="cloud-settings-field">
					<label>{{ __("Billing address") }} <span class="cloud-settings-req">*</span></label>
					<input v-model="form.address_line1" class="cloud-settings-input"
						:placeholder="__('Street address')" :disabled="working" />
				</div>

				<div class="cloud-settings-form-grid">
					<div class="cloud-settings-field">
						<label>{{ __("City") }} <span class="cloud-settings-req">*</span></label>
						<input v-model="form.city" class="cloud-settings-input" :disabled="working" />
					</div>
					<div class="cloud-settings-field">
						<label>{{ __("State") }} <span class="cloud-settings-req">*</span></label>
						<input v-model="form.state" class="cloud-settings-input" :disabled="working" />
					</div>
				</div>

				<div class="cloud-settings-form-grid">
					<div class="cloud-settings-field">
						<label>{{ __("Country") }} <span class="cloud-settings-req">*</span></label>
						<input v-model="form.country" class="cloud-settings-input" :disabled="working" />
					</div>
					<div class="cloud-settings-field">
						<label>{{ __("PIN / ZIP") }} <span class="cloud-settings-req">*</span></label>
						<input v-model="form.pincode" class="cloud-settings-input" :disabled="working" />
					</div>
				</div>


				<div class="cloud-settings-form-grid">
				<div class="cloud-settings-field" style="max-width: 160px">
					<label>{{ __("Currency") }} <span class="cloud-settings-req">*</span></label>
					<SelectMenu v-model="form.currency" :options="currencyOptions" :placeholder="__('Select')" />
				</div>
				<div class="cloud-settings-field">
					<label>{{ __("GSTIN") }}</label>
					<input v-model="form.gstin" class="cloud-settings-input"
						placeholder="29ABCDE1234F1Z5" :disabled="working" />
				</div>
			</div>
			</div>

			<div class="cloud-settings-actions" style="justify-content: flex-end">
				<button class="btn btn-sm btn-default" :disabled="working" @click="$emit('close')">
					{{ __("Cancel") }}
				</button>
				<button class="btn btn-sm btn-primary" :disabled="!canSave" @click="save">
					{{ __("Save") }}
				</button>
			</div>
		</template>
	</div>
</template>
