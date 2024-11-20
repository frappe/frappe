import Visa from './logo/Visa.vue'
import MasterCard from './logo/MasterCard.vue'
import Amex from './logo/Amex.vue'
import JCB from './logo/JCB.vue'
import UnionPay from './logo/UnionPay.vue'
import Generic from './logo/Generic.vue'
import { FeatherIcon } from 'frappe-ui'
import { h } from 'vue'

export function calculateTrialEndDays(trialEndDate) {
	if (!trialEndDate) return 0

	trialEndDate = new Date(trialEndDate)
	const today = new Date()
	const diffTime = trialEndDate - today
	const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
	return diffDays
}

export function currency(value, currency, fractions = 2) {
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency,
		maximumFractionDigits: fractions,
	}).format(value)
}

export function cardBrandIcon(brand) {
	let component = {
		'master-card': MasterCard,
		mastercard: MasterCard,
		visa: Visa,
		amex: Amex,
		jcb: JCB,
		generic: Generic,
		'union-pay': UnionPay,
	}[brand || 'generic']

	if (!component) {
		component = Generic
	}

	return h(component, { class: 'size-6' })
}

export function parseSize(sizeInMB) {
	if (sizeInMB < 1024) {
		return `${sizeInMB} MB`
	} else {
		return `${(sizeInMB / 1024).toFixed(0)} GB`
	}
}

export const ConfirmMessage = {
	name: 'ConfirmMessage',
	props: {
		price: String,
		currency: String,
	},
	render() {
		return h('div', { class: 'text-base' }, [
			h('div', {}, [
				'Are you sure you want to change your plan to ',
				h('b', {}, `${this.currency}${this.price}`),
				'/mo?',
			]),
			h(
				'div',
				{ class: 'text-gray-600 inline-flex gap-1 mt-3' },
				h(FeatherIcon, { name: 'info', class: 'h-4' }),
				'Your site will be in maintenance mode for some time.'
			),
		])
	},
}
