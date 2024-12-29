<template>
	<header class="flex h-10.5 border-b items-center justify-between py-2 px-5 shrink-0">
		<Breadcrumbs :items="[{ label: 'Invoices' }]" />
	</header>
	<div class="flex flex-col overflow-hidden px-60 pt-6">
		<ListView
			:columns="columns"
			:rows="rows"
			row-key="id"
			:options="{
				selectable: false,
			}"
		>
			<ListHeader />
			<ListRows>
				<ListRow v-for="row in rows" :key="row.id" v-slot="{ column, item }" :row="row">
					<ListRowItem :item="item" :align="column.align">
						<template #prefix>
							<InvoiceIcon v-if="column.key == 'name'" class="h-4" />
						</template>
						<Badge
							v-if="column.key == 'status'"
							:label="item.label"
							variant="subtle"
							:theme="item.color"
							size="md"
						/>
						<Button
							v-if="
								column.key == 'button' &&
								item.status == 'Unpaid' &&
								item.amount_due > 0
							"
							label="Pay now"
							@click.stop="item.payNow"
						>
							<template #prefix>
								<FeatherIcon name="external-link" class="h-4 w-4" />
							</template>
						</Button>
						<Button
							v-else-if="column.key == 'button' && item.url"
							label="Download"
							@click.stop="item.download"
						>
							<template #prefix>
								<FeatherIcon name="download" class="h-4 w-4" />
							</template>
						</Button>
					</ListRowItem>
				</ListRow>
			</ListRows>
		</ListView>
	</div>
</template>
<script setup>
import InvoiceIcon from '@/icons/InvoiceIcon.vue'
import {
	ListView,
	ListHeader,
	ListRows,
	ListRow,
	ListRowItem,
	FeatherIcon,
	Button,
	Badge,
	createResource,
	Breadcrumbs,
} from 'frappe-ui'
import { computed, inject } from 'vue'

const team = inject('team')

const invoices = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.get_invoices' },
	cache: 'invoices',
	auto: true,
})

const columns = [
	{
		label: 'Invoice',
		key: 'name',
		width: 1.2,
	},
	{
		label: 'Status',
		key: 'status',
		width: 0.8,
	},
	{
		label: 'Period',
		key: 'due_date',
		width: 1.5,
	},
	{
		label: 'Total',
		key: 'total',
		width: 1,
	},
	{
		label: '',
		key: 'button',
		width: 1,
		align: 'right',
	},
]

const rows = computed(() => {
	if (!team.data) return []
	return invoices.data?.map((invoice) => {
		// Set name based on invoice type
		let name = 'Prepaid Credits'
		if (invoice.type == 'Subscription') {
			name = new Date(invoice.period_end).toLocaleString('en-US', {
				month: 'long',
				year: 'numeric',
			})
		}

		// Set due date based on invoice type
		let due_date = new Date(invoice.due_date).toLocaleString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
		})
		if (invoice.type == 'Subscription') {
			let start = new Date(invoice.period_start)
			let end = new Date(invoice.period_end)
			let sameYear = start.getFullYear() === end.getFullYear()
			let formattedStart = sameYear
				? start.toLocaleString('en-US', { month: 'short', day: 'numeric' })
				: start.toLocaleString('en-US', { dateStyle: 'short' })
			let formattedEnd = end.toLocaleString('en-US', {
				year: 'numeric',
				month: 'short',
				day: 'numeric',
			})
			due_date = `${formattedStart} - ${formattedEnd}`
		}

		return {
			id: invoice.name,
			name: name,
			status: {
				label: invoice.status,
				color:
					invoice.status === 'Paid'
						? 'green'
						: invoice.status == 'Unpaid'
						? 'orange'
						: 'gray',
			},
			due_date: due_date,
			total: formatCurrency(invoice.total),
			button: {
				url: invoice.invoice_pdf,
				download: () => downloadInvoice(invoice.name),
				status: invoice.status,
				amount_due: invoice.amount_due,
				payNow: () => payNow(invoice),
			},
		}
	})
})

function payNow(invoice) {
	if (invoice.stripe_invoice_url) {
		window.open(invoice.stripe_invoice_url, '_blank')
	} else {
		createResource({
			url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
			params: {
				method: 'billing.get_stripe_payment_url_for_invoice',
				data: { name: invoice.name },
			},
			auto: true,
			onSuccess: (url) => window.open(url, '_blank'),
		})
	}
}

function downloadInvoice(invoice) {
	createResource({
		url: 'frappe.integrations.frappe_providers.frappecloud_billing.get_token_and_base_url',
		auto: true,
		onSuccess: (data) => {
			fetch(`${data.base_url}/api/method/press.saas.api.billing.download_invoice`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-Site-Access-Token': data.token,
				},
				body: JSON.stringify({ name: invoice }),
			})
				.then((response) => {
					if (!response.ok) {
						throw new Error('Network response was not ok ' + response.statusText)
					}
					return response.blob()
				})
				.then((blob) => {
					const url = window.URL.createObjectURL(blob)
					window.open(url, '_blank')
				})
				.catch((error) => {
					console.error('There was a problem with the fetch operation:', error)
				})
		},
	})
}

function formatCurrency(value) {
	if (value === 0) {
		return ''
	}
	return userCurrency(value)
}

function currency(value, currency, fractions = 2) {
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency,
		maximumFractionDigits: fractions,
	}).format(value)
}

function userCurrency(value, fractions = 2) {
	return currency(value, team.data?.currency, fractions)
}
</script>
