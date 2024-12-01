<template>
	<div>
		<!-- Amount -->
		<div>
			<FormControl
				:label="`Amount (Minimum Amount: ${minimumAmount})`"
				class="mb-3"
				v-model.number="creditsToBuy"
				name="amount"
				autocomplete="off"
				type="number"
				:min="minimumAmount"
			>
				<template #prefix>
					<div class="grid w-4 place-items-center text-sm text-gray-700">
						{{ team.data.currency === 'INR' ? '₹' : '$' }}
					</div>
				</template>
			</FormControl>
			<FormControl
				v-if="team.data.currency === 'INR'"
				:label="`Total Amount + GST (${team.data?.billing_info.gst_percentage * 100}%)`"
				disabled
				:modelValue="totalAmount"
				name="total"
				autocomplete="off"
				type="number"
			>
				<template #prefix>
					<div class="grid w-4 place-items-center text-sm text-gray-700">
						{{ team.data.currency === 'INR' ? '₹' : '$' }}
					</div>
				</template>
			</FormControl>
		</div>

		<!-- Payment Gateway -->
		<div class="mt-4">
			<div class="text-xs text-gray-600">Select Payment Gateway</div>
			<div class="mt-1.5 grid grid-cols-1 gap-2 sm:grid-cols-2">
				<Button
					v-if="team.data.currency === 'INR' || team.data.razorpay_enabled"
					size="lg"
					:class="{
						'border-gray-700 border-[1.5px]': paymentGateway === 'Razorpay',
					}"
					@click="paymentGateway = 'Razorpay'"
				>
					<RazorpayLogo class="w-24" />
				</Button>
				<Button
					size="lg"
					:class="{
						'border-gray-700 border-[1.5px]': paymentGateway === 'Stripe',
					}"
					@click="paymentGateway = 'Stripe'"
				>
					<StripeLogo class="h-7 w-24" />
				</Button>
			</div>
		</div>

		<!-- Payment Button -->
		<BuyCreditsStripe
			v-if="paymentGateway === 'Stripe'"
			:amount="creditsToBuy"
			:minimumAmount="minimumAmount"
			@success="() => emit('success')"
			@cancel="show = false"
		/>

		<BuyCreditsRazorpay
			v-if="paymentGateway === 'Razorpay'"
			:amount="creditsToBuy"
			:minimumAmount="minimumAmount"
			@success="() => emit('success')"
			@cancel="show = false"
		/>
	</div>
</template>
<script setup>
import BuyCreditsStripe from './BuyCreditsStripe.vue'
import BuyCreditsRazorpay from './BuyCreditsRazorpay.vue'
import RazorpayLogo from '../logo/RazorpayLogo.vue'
import StripeLogo from '../logo/StripeLogo.vue'
import { FormControl, Button, createResource } from 'frappe-ui'
import { ref, computed, inject } from 'vue'

const emit = defineEmits(['success'])

const team = inject('team')

const totalUnpaidAmount = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.total_unpaid_amount' },
	cache: 'totalUnpaidAmount',
	auto: true,
})

const minimumAmount = computed(() => {
	if (!team.data) return 0
	const unpaidAmount = totalUnpaidAmount.data || 0
	const minimumDefault = team.data?.currency == 'INR' ? 410 : 5

	return Math.ceil(unpaidAmount && unpaidAmount > 0 ? unpaidAmount : minimumDefault)
})

const creditsToBuy = ref(minimumAmount.value)
const paymentGateway = ref('')

const totalAmount = computed(() => {
	let _creditsToBuy = creditsToBuy.value || 0
	if (team.data?.currency === 'INR') {
		return (
			_creditsToBuy +
			_creditsToBuy * (team.data.billing_info.gst_percentage || 0)
		).toFixed(2)
	} else {
		return _creditsToBuy
	}
})
</script>
