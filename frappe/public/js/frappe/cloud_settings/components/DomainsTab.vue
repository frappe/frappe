<template>
	<div>
		<div class="cloud-settings-stack">
			<div class="cloud-settings-toolbar">
				<input
					v-model="domainInput"
					class="cloud-settings-input"
					:placeholder="__('shop.mycompany.in')"
					:disabled="working"
					@keyup.enter="previewDomain"
				/>
				<button class="btn btn-sm btn-default" :disabled="!canAdd" @click="previewDomain">
					{{ __("Add") }}
				</button>
			</div>

			<div v-if="error" class="cloud-settings-alert error">
				<svg class="icon icon-sm"><use href="#icon-triangle-alert"></use></svg>
				<span>{{ error }}</span>
			</div>

			<div v-if="dnsRecords.length" class="cloud-settings-card">
				<div class="cloud-settings-title-lg" style="font-size: var(--text-base)">
					{{ pendingDomain }}
				</div>
				<p class="cloud-settings-sub">{{ __("Add these DNS records, then continue.") }}</p>
				<div class="cloud-settings-dns" style="margin: 14px 0">
					<div
						v-for="(record, index) in dnsRecords"
						:key="index"
						class="cloud-settings-dns-record"
					>
						<span>{{ record.type }}</span>
						<code>{{ record.host }}</code>
						<code>{{ record.value }}</code>
					</div>
				</div>
				<div class="cloud-settings-actions">
					<button
						class="btn btn-sm btn-default"
						:disabled="working"
						@click="clearPreview"
					>
						{{ __("Cancel") }}
					</button>
					<button class="btn btn-sm btn-primary" :disabled="working" @click="confirmAdd">
						{{ __("Add domain") }}
					</button>
				</div>
			</div>

			<div v-if="!domains" class="cloud-settings-state">{{ __("Loading") }}</div>
			<template v-else>
				<div
					v-for="domain in domains"
					:key="domain.domain"
					class="cloud-settings-card cloud-settings-row"
				>
					<div>
						<div class="cloud-settings-domain-name">
							{{ domain.domain }}
							<svg class="icon icon-xs"><use href="#icon-lock"></use></svg>
						</div>
						<p class="cloud-settings-sub">{{ subtitle(domain) }}</p>
					</div>
					<div class="cloud-settings-actions">
						<span v-if="domain.is_primary" class="cloud-settings-badge">{{
							__("Primary")
						}}</span>
						<button
							v-else
							class="btn btn-sm btn-default"
							:disabled="working"
							@click="makePrimary(domain.domain)"
						>
							{{ __("Make primary") }}
						</button>
						<button
							v-if="!domain.is_default"
							class="btn btn-sm btn-default"
							:disabled="working"
							@click="remove(domain.domain)"
						>
							{{ __("Remove") }}
						</button>
					</div>
				</div>

				<p v-if="domains.length <= 1" class="cloud-settings-help">
					{{
						__(
							"No custom domains yet. Add one above and we'll handle SSL once DNS checks out."
						)
					}}
				</p>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { usePanelHeader } from "../panel";

const store = inject("store");

usePanelHeader(__("Domains"), __("The addresses this site answers on."));

const domainInput = ref("");
const pendingDomain = ref("");
const dnsRecords = ref([]);
const working = ref(false);

onMounted(store.loadDomains);

const domains = computed(() => store.state.domains?.domains);
const error = computed(() => store.state.domainsError);
const canAdd = computed(() => domainInput.value.trim() && !working.value);

async function previewDomain() {
	const domain = domainInput.value.trim();
	if (!domain) return;
	await run(async () => {
		const response = await store.api.getDomainDnsRecords(domain);
		dnsRecords.value = response.records || [];
		pendingDomain.value = domain;
		if (!dnsRecords.value.length) await confirmAdd();
	});
}

async function confirmAdd() {
	const domain = pendingDomain.value || domainInput.value.trim();
	if (!domain) return;
	await run(async () => {
		await store.api.addDomain(domain);
		clearPreview();
		await store.loadDomains(true);
	});
}

async function makePrimary(domain) {
	await run(async () => {
		await store.api.setPrimaryDomain(domain);
		await store.loadDomains(true);
	});
}

async function remove(domain) {
	await run(async () => {
		await store.api.removeDomain(domain);
		await store.loadDomains(true);
	});
}

async function run(action) {
	working.value = true;
	store.state.domainsError = "";
	try {
		await action();
	} catch (exception) {
		store.state.domainsError = store.api.getErrorMessage(exception);
	} finally {
		working.value = false;
	}
}

function clearPreview() {
	dnsRecords.value = [];
	pendingDomain.value = "";
	domainInput.value = "";
}

function subtitle(domain) {
	return domain.is_default ? __("Default address · managed SSL") : __("Managed SSL");
}
</script>
