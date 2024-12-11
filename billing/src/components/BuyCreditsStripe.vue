<template>
	<div>
		<label
			class="block"
			:class="{
				'pointer-events-none h-0.5 opacity-0': step != 'Add Card Details',
				'mt-4': step == 'Add Card Details',
			}"
		>
			<span class="text-sm leading-4 text-gray-700"> Credit or Debit Card </span>
			<div class="form-input mt-2 block w-full pl-3" ref="cardElementRef"></div>
			<ErrorMessage class="mt-1" :message="cardErrorMessage" />
		</label>

		<div v-if="step == 'Setting up Stripe'" class="mt-8 flex justify-center">
			<Spinner class="h-4 w-4 text-gray-700" />
		</div>
		<ErrorMessage class="mt-2" :message="createPaymentIntent.error || errorMessage" />
		<div class="mt-8">
			<Button
				v-if="step == 'Get Amount'"
				class="w-full"
				size="md"
				variant="solid"
				label="Proceed to payment using Stripe"
				:loading="createPaymentIntent.loading"
				@click="createPaymentIntent.submit()"
			/>
			<Button
				v-else-if="step == 'Add Card Details'"
				class="w-full"
				size="md"
				variant="solid"
				label="Make payment via Stripe"
				:loading="paymentInProgress"
				@click="onBuyClick"
			/>
		</div>
	</div>
</template>
<script setup>
import { Button, ErrorMessage, Spinner, createResource, toast } from 'frappe-ui'
import { loadStripe } from '@stripe/stripe-js'
import { ref, nextTick, inject } from 'vue'

const props = defineProps({
	amount: {
		type: Number,
		default: 0,
	},
	minimumAmount: {
		type: Number,
		default: 0,
	},
})

const emit = defineEmits(['success'])

const team = inject('team')

const step = ref('Get Amount')
const clientSecret = ref(null)
const cardErrorMessage = ref(null)
const errorMessage = ref(null)
const paymentInProgress = ref(false)

const stripe = ref(null)
const card = ref(null)
const elements = ref(null)
const ready = ref(false)

const cardElementRef = ref(null)

const createPaymentIntent = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: {
		method: 'billing.create_payment_intent_for_buying_credits',
		data: { amount: props.amount },
	},
	validate() {
		if (props.amount < props.minimumAmount && !team.data.erpnext_partner) {
			return `Amount must be greater than or equal to ${props.minimumAmount}`
		}
	},
	async onSuccess(data) {
		step.value = 'Setting up Stripe'
		let { publishable_key, client_secret } = data
		clientSecret.value = client_secret
		stripe.value = await loadStripe(publishable_key)
		elements.value = stripe.value.elements()
		const style = {
			base: {
				color: '#171717',
				fontFamily: [
					'ui-sans-serif',
					'system-ui',
					'-apple-system',
					'BlinkMacSystemFont',
					'"Segoe UI"',
					'Roboto',
					'"Helvetica Neue"',
					'Arial',
					'"Noto Sans"',
					'sans-serif',
					'"Apple Color Emoji"',
					'"Segoe UI Emoji"',
					'"Segoe UI Symbol"',
					'"Noto Color Emoji"',
				].join(', '),
				fontSmoothing: 'antialiased',
				fontSize: '13px',
				'::placeholder': {
					color: '#C7C7C7',
				},
			},
			invalid: {
				color: '#7C7C7C',
				iconColor: '#7C7C7C',
			},
		}
		card.value = elements.value.create('card', {
			hidePostalCode: true,
			style: style,
			classes: {
				complete: '',
				focus: 'bg-gray-100',
			},
		})

		step.value = 'Add Card Details'
		nextTick(() => {
			card.value.mount(cardElementRef.value)
		})

		card.value.addEventListener('change', (event) => {
			cardErrorMessage.value = event.error?.message || null
		})
		card.value.addEventListener('ready', () => {
			ready.value = true
		})
	},
})

async function onBuyClick() {
	paymentInProgress.value = true
	let payload = await stripe.value.confirmCardPayment(clientSecret.value, {
		payment_method: { card: card.value },
	})

	if (payload.error) {
		errorMessage.value = payload.error.message
		paymentInProgress.value = false
	} else {
		toast({
			position: 'bottom-right',
			title: 'Payment successful',
			text: 'Payment processed successfully, we will update your account shortly on confirmation from Stripe',
			icon: 'check',
			iconClasses: 'text-green-600',
			timeout: 10,
		})
		paymentInProgress.value = false
		emit('success')
		errorMessage.value = null
	}
}
</script>
