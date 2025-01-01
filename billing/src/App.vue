<template>
	<div v-if="isFCSite.data && user.name" class="flex h-screen w-screen">
		<div class="h-full border-r bg-gray-50">
			<AppSidebar />
		</div>
		<div class="flex-1 flex flex-col h-full overflow-x-hidden">
			<router-view />
		</div>
		<Dialogs />
		<Toasts />
	</div>
	<PageNotFound v-else />
</template>

<script setup>
import PageNotFound from './pages/PageNotFound.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { Dialogs } from '@/dialogs.js'
import { getSession } from '@/session.js'
import { Toasts, createResource } from 'frappe-ui'
import { provide } from 'vue'

const { isFCSite, user } = getSession()

const team = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'team.info' },
	cache: 'team',
	auto: true,
})

const currentSiteInfo = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.current_site_info',
	auto: true,
	cache: 'currentSiteInfo',
})

provide('team', team)
provide('currentSiteInfo', currentSiteInfo)
</script>
