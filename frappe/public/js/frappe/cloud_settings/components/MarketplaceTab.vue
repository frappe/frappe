<template>
	<div class="cloud-settings-marketplace">
		<div v-if="error" class="cloud-settings-alert error">{{ error }}</div>
		<MarketplaceSkeleton v-else-if="!marketplace" />

		<template v-else>
			<div class="cloud-settings-toolbar">
				<SearchInput v-model="query" :placeholder="__('Search apps')" />
				<SelectMenu
					v-model="category"
					:options="marketplace.categories"
					:placeholder="__('All categories')"
				/>
			</div>

			<!-- Only the app list scrolls; the toolbar above stays fixed. -->
			<div class="cloud-settings-apps-catalog">
				<div v-if="!filteredApps.length" class="cloud-settings-state">
					{{ __("No apps match your search.") }}
				</div>
				<div v-else class="cloud-settings-apps">
					<MarketplaceApp
						v-for="app in filteredApps"
						:key="app.name"
						:app="app"
						:pending="pending[app.name] || ''"
						:error="errors[app.name] || ''"
						@install="install"
						@uninstall="uninstall"
						@update="updateOne"
					/>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref, watchEffect } from "vue";
import { waitForTask } from "../store";
import MarketplaceApp from "./MarketplaceApp.vue";
import MarketplaceSkeleton from "./MarketplaceSkeleton.vue";
import SearchInput from "./SearchInput.vue";
import SelectMenu from "./SelectMenu.vue";

const store = inject("store");
const panel = inject("panel");

const title = __("Marketplace");
const description = __("Install apps and keep them up to date.");

// Wording per action, so every toast names both the action and the app.
const ACTION = {
	install: { progress: __("Installing"), done: __("installed"), verb: __("install") },
	uninstall: { progress: __("Uninstalling"), done: __("uninstalled"), verb: __("uninstall") },
	update: { progress: __("Updating"), done: __("updated"), verb: __("update") },
};

const query = ref("");
const category = ref("");
const pending = reactive({});
const errors = reactive({});
const updatingAll = ref(false);

let unmounted = false;
onBeforeUnmount(() => (unmounted = true));
onMounted(store.loadMarketplace);

const marketplace = computed(() => store.state.marketplace);
const error = computed(() => store.state.marketplaceError);
const updateCount = computed(() => marketplace.value?.update_count || 0);

// Drive the SettingsDialog panel header: title, description and a reactive
// "Update all" action that appears only when updates are available.
watchEffect(() => {
	const actions = [];
	if (updateCount.value) {
		actions.push({
			label: updatingAll.value
				? __("Updating")
				: __("Update all ({0})", [updateCount.value]),
			primary: true,
			click: () => !updatingAll.value && updateAll(),
		});
	}
	panel.set_header({ title, description, actions });
});

const filteredApps = computed(() => {
	const apps = marketplace.value?.apps || [];
	const term = query.value.trim().toLowerCase();
	return apps.filter((app) => {
		if (category.value && app.category !== category.value) return false;
		if (!term) return true;
		return `${app.title} ${app.description}`.toLowerCase().includes(term);
	});
});

function install(app) {
	return runAction(app, "install", () => store.api.installApp(app.name));
}

function uninstall(app) {
	return runAction(app, "uninstall", () => store.api.uninstallApp(app.name));
}

function updateOne(app) {
	return runAction(app, "update", () => store.api.updateApps([app.name]));
}

async function updateAll() {
	updatingAll.value = true;
	try {
		const { task_id } = await store.api.updateApps();
		await settle(task_id, ACTION.update, __("all apps"));
		await store.loadMarketplace(true);
	} catch (exception) {
		notify(store.api.getErrorMessage(exception, exception.message), "red");
	} finally {
		updatingAll.value = false;
	}
}

// Start the action, then track its bench task to completion, keeping the row in
// its pending state the whole time and reflecting success/failure/abandonment.
async function runAction(app, verb, action) {
	errors[app.name] = "";
	pending[app.name] = verb;
	try {
		const { task_id } = await action();
		await settle(task_id, ACTION[verb], app.title);
		await store.loadMarketplace(true);
	} catch (exception) {
		errors[app.name] = store.api.getErrorMessage(exception, exception.message);
		notify(errors[app.name], "red");
	} finally {
		delete pending[app.name];
	}
}

// Resolve a task's outcome into a user-facing message. Throws on failure so the
// caller records an error state; a timed-out or lost task is surfaced as a
// warning because it may still be running on the server.
async function settle(taskId, action, label) {
	if (!taskId) return;
	const outcome = await waitForTask(taskId, () => unmounted);
	if (outcome === "cancelled") return;
	if (outcome === "success") {
		notify(__("{0} {1}.", [label, action.done]), "green");
	} else if (outcome === "failed" || outcome === "error") {
		throw new Error(__("Couldn't {0} {1}.", [action.verb, label]));
	} else {
		// timeout or gone — still running or lost track; don't claim done.
		notify(
			__(
				"{0} {1} is taking longer than expected. It will keep running in the background — refresh to check.",
				[action.progress, label]
			),
			"orange"
		);
	}
}

function notify(message, indicator = "green") {
	frappe.show_alert({ message, indicator });
}
</script>
