<template>
	<div class="relative">
		<div
			v-if="!ready"
			class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-8 transform"
		>
			<Spinner class="h-5 w-5 text-gray-700" />
		</div>
		<div :class="{ 'opacity-0': !ready }">
			<div v-show="!tryingMicroCharge">
				<label class="block">
					<span class="block text-xs text-gray-600"> Credit or Debit Card </span>
					<div
						class="form-input mt-2 block h-[unset] w-full py-2 pl-3"
						ref="cardElementRef"
					></div>
					<ErrorMessage class="mt-1" :message="cardErrorMessage" />
				</label>
				<FormControl
					class="mt-4"
					label="Name on Card"
					type="text"
					v-model="billingInformation.cardHolderName"
				/>
				<AddressForm
					ref="addressFormRef"
					class="mt-5"
					v-model="billingInformation"
					@success="console.log('Address form submitted')"
				/>
			</div>

			<div class="mt-3 space-y-4" v-show="tryingMicroCharge">
				<p class="text-base text-gray-700">
					We are attempting to charge your card with
					<strong>{{ formattedMicroChargeAmount }}</strong> to make sure the card works.
					This amount will be <strong>refunded</strong> back to your account.
				</p>

				<Button :loading="!microChargeCompleted" :loadingText="'Verifying Card'">
					Card Verified
					<template #prefix>
						<GreenCheckIcon class="h-4 w-4" />
					</template>
				</Button>
			</div>

			<ErrorMessage class="mt-2" :message="errorMessage" />

			<div class="mt-6 flex items-center justify-between">
				<PoweredByStripeLogo />
				<Button
					v-if="showAddAnotherCardButton"
					label="Add Another Card"
					@click="clearForm"
				>
					<template #prefix>
						<FeatherIcon class="h-4" name="plus" />
					</template>
				</Button>
				<Button
					v-else-if="!tryingMicroCharge"
					variant="solid"
					label="Verify & Save Card"
					:loading="addingCard"
					@click="submit"
				/>
			</div>
		</div>
	</div>
</template>
<script setup>
import AddressForm from './AddressForm.vue'
import PoweredByStripeLogo from '../logo/PoweredByStripeLogo.vue'
import GreenCheckIcon from '../icons/GreenCheckIcon.vue'
import {
	FeatherIcon,
	Button,
	FormControl,
	Spinner,
	ErrorMessage,
	createResource,
	toast,
} from 'frappe-ui'
import { currency } from '../utils.js'
import { loadStripe } from '@stripe/stripe-js'
import { ref, reactive, computed, inject, onMounted } from 'vue'

const emit = defineEmits(['success'])

const team = inject('team')

const stripe = ref(null)
const elements = ref(null)
const card = ref(null)
const ready = ref(false)
const _setupIntent = ref(null)
const errorMessage = ref(null)
const cardErrorMessage = ref(null)
const addingCard = ref(false)
const tryingMicroCharge = ref(false)
const showAddAnotherCardButton = ref(false)
const microChargeCompleted = ref(false)

onMounted(() => setupStripeIntent())

const cardElementRef = ref(null)

const getPublishedKeyAndSetupIntent = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.get_publishable_key_and_setup_intent' },
	onSuccess: async (data) => {
		const { publishable_key, setup_intent } = data
		_setupIntent.value = setup_intent
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
				color: '#C7C7C7',
				iconColor: '#C7C7C7',
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
		card.value.mount(cardElementRef.value)
		card.value.addEventListener('change', (event) => {
			cardErrorMessage.value = event.error?.message || null
		})
		card.value.addEventListener('ready', () => {
			ready.value = true
		})
	},
})

const countryList = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.country_list' },
	cache: 'countryList',
	auto: true,
})

const browserTimezone = computed(() => {
	if (!window.Intl) {
		return null
	}
	return Intl.DateTimeFormat().resolvedOptions().timeZone
})

const billingInformation = reactive({
	cardHolderName: '',
	country: '',
	gstin: '',
})

createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: {
		method: 'billing.get_information',
		data: { timezone: browserTimezone.value },
	},
	auto: true,
	onSuccess: (data) => {
		billingInformation.country = data?.country
		billingInformation.address = data?.address_line1
		billingInformation.city = data?.city
		billingInformation.state = data?.state
		billingInformation.postal_code = data?.pincode
		billingInformation.gstin = data?.gstin == 'Not Applicable' ? '' : data?.gstin
	},
})

const setupIntentSuccess = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	makeParams: ({ setupIntent }) => {
		return {
			method: 'billing.setup_intent_success',
			data: {
				setup_intent: setupIntent,
				address: billingInformation,
			},
		}
	},
	onSuccess: async ({ payment_method_name }) => {
		await verifyWithMicroChargeIfApplicable(payment_method_name)
		addingCard.value = false
		toast({
			title: 'Card added successfully',
			icon: 'check',
			iconClasses: 'text-green-600',
			position: 'bottom-right',
		})
	},
	onError: (error) => {
		console.error(error)
		addingCard.value = false
		errorMessage.value = error.messages.join('\n')
		toast({
			title: errorMessage.value,
			icon: 'x',
			iconClasses: 'text-red-600',
			position: 'bottom-right',
		})
	},
})

const verifyCardWithMicroCharge = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	makeParams: ({ paymentMethodName }) => {
		return {
			method: 'billing.create_payment_intent_for_micro_debit',
			data: { payment_method_name: paymentMethodName },
		}
	},
})

async function setupStripeIntent() {
	await getPublishedKeyAndSetupIntent.submit()
	const { first_name, last_name = '' } = team.data?.user_info
	const fullname = first_name + ' ' + last_name
	billingInformation.cardHolderName = fullname.trimEnd()
}

const addressFormRef = ref(null)

async function submit() {
	addingCard.value = true
	let message = await addressFormRef.value.validate()

	if (message) {
		errorMessage.value = message
		addingCard.value = false
		return
	} else {
		errorMessage.value = null
	}

	const { setupIntent, error } = await stripe.value.confirmCardSetup(
		_setupIntent.value.client_secret,
		{
			payment_method: {
				card: card.value,
				billing_details: {
					name: billingInformation.cardHolderName,
					address: {
						line1: billingInformation.address,
						city: billingInformation.city,
						state: billingInformation.state,
						postal_code: billingInformation.postal_code,
						country: getCountryCode(team.data?.country),
					},
				},
			},
		}
	)
	if (error) {
		addingCard.value = false
		let declineCode = error.decline_code
		let _errorMessage = error.message
		if (declineCode === 'do_not_honor') {
			errorMessage.value =
				"Your card was declined. It might be due to insufficient funds or you might've exceeded your daily limit. Please try with another card or contact your bank."
			showAddAnotherCardButton.value = true
		} else if (declineCode === 'transaction_not_allowed') {
			errorMessage.value =
				'Your card was declined. It might be due to restrictions on your card, like international transactions or online payments. Please try with another card or contact your bank.'
			showAddAnotherCardButton.value = true
		} else if (_errorMessage != 'Your card number is incomplete.') {
			errorMessage.value = _errorMessage
		}
	} else {
		if (setupIntent?.status === 'succeeded') {
			setupIntentSuccess.submit({ setupIntent })
		}
	}
}

async function verifyWithMicroChargeIfApplicable(paymentMethodName) {
	const teamCurrency = team.data?.currency
	const verifyCardsWithMicroCharge = window.verify_cards_with_micro_charge
	const isMicroChargeApplicable =
		verifyCardsWithMicroCharge === 'Both INR and USD' ||
		(verifyCardsWithMicroCharge == 'Only INR' && teamCurrency === 'INR') ||
		(verifyCardsWithMicroCharge === 'Only USD' && teamCurrency === 'USD')
	if (isMicroChargeApplicable) {
		await _verifyWithMicroCharge(paymentMethodName)
	} else {
		emit('success')
	}
}

async function _verifyWithMicroCharge(paymentMethodName) {
	tryingMicroCharge.value = true
	return verifyCardWithMicroCharge.submit({
		paymentMethodName,
		onSuccess: async (paymentIntent) => {
			let { client_secret } = paymentIntent
			let payload = await stripe.value.confirmCardPayment(client_secret, {
				payment_method: { card: card.value },
			})
			if (payload.paymentIntent?.status === 'succeeded') {
				microChargeCompleted.value = true
				emit('success')
			}
		},
		onError: (error) => {
			console.error(error)
			tryingMicroCharge.value = false
			errorMessage.value = error.messages.join('\n')
		},
	})
}

function getCountryCode(country) {
	let code = countryList.data.find((d) => d.name === country).code
	return code.toUpperCase()
}

async function clearForm() {
	ready.value = false
	errorMessage.value = null
	showAddAnotherCardButton.value = false
	card.value = null
	setupStripeIntent()
}

const formattedMicroChargeAmount = computed(() => {
	if (!team.data?.currency) {
		return 0
	}
	return currency(team.data?.billing_info?.micro_debit_charge_amount, team.data?.currency)
})
</script>
