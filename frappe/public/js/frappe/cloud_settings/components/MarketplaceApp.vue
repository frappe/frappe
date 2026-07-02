<template>
	<div class="cloud-settings-app">
		<img
			v-if="app.logo_url && !imageFailed"
			class="cloud-settings-app-logo"
			:src="app.logo_url"
			:alt="app.title"
			loading="lazy"
			decoding="async"
			@error="imageFailed = true"
		/>
		<div v-else class="cloud-settings-app-logo placeholder">{{ initial }}</div>

		<div class="cloud-settings-app-body">
			<div class="cloud-settings-app-name">
				<span class="cloud-settings-app-title" :title="app.title">{{ app.title }}</span>
				<span class="cloud-settings-app-version">
					<template v-if="app.installed && app.has_update">
						v{{ app.installed_version }}
						<span class="next">→ v{{ app.latest_version }}</span>
					</template>
					<template v-else-if="app.installed && app.installed_version">
						v{{ app.installed_version }}
					</template>
					<template v-else-if="app.latest_version">v{{ app.latest_version }}</template>
				</span>
			</div>
			<div class="cloud-settings-app-desc" :title="app.description">
				{{ app.description }}
			</div>
		</div>

		<div class="cloud-settings-app-action">
			<svg
				v-if="error && !busy"
				class="icon icon-xs cloud-settings-app-error"
				:title="error"
			>
				<use href="#icon-triangle-alert"></use>
			</svg>

			<span
				v-if="!app.installed && !app.installable"
				class="cloud-settings-app-incompatible"
				:title="incompatibleReason"
			>
				{{ __("Incompatible") }}
			</span>

			<template v-else-if="!app.installed">
				<button
					class="btn btn-sm btn-default"
					:disabled="busy"
					@click="$emit('install', app)"
				>
					<svg v-if="pending === 'install'" class="icon icon-xs cloud-settings-spinner">
						<use href="#icon-loader-circle"></use>
					</svg>
					{{ pending === "install" ? __("Installing") : __("Install") }}
				</button>
			</template>

			<template v-else-if="app.has_update">
				<button
					class="btn btn-sm btn-primary"
					:disabled="busy"
					@click="$emit('update', app)"
				>
					<svg v-if="pending === 'update'" class="icon icon-xs cloud-settings-spinner">
						<use href="#icon-loader-circle"></use>
					</svg>
					{{ pending === "update" ? __("Updating") : __("Update") }}
				</button>
				<button
					class="btn btn-sm btn-default"
					:disabled="busy"
					@click="$emit('uninstall', app)"
				>
					<svg
						v-if="pending === 'uninstall'"
						class="icon icon-xs cloud-settings-spinner"
					>
						<use href="#icon-loader-circle"></use>
					</svg>
					{{ pending === "uninstall" ? __("Uninstalling") : __("Uninstall") }}
				</button>
			</template>

			<button
				v-else
				class="btn btn-sm btn-default"
				:disabled="busy"
				@click="$emit('uninstall', app)"
			>
				<svg v-if="pending === 'uninstall'" class="icon icon-xs cloud-settings-spinner">
					<use href="#icon-loader-circle"></use>
				</svg>
				{{ pending === "uninstall" ? __("Uninstalling") : __("Uninstall") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
	app: { type: Object, required: true },
	// Action verb while this app's task runs: "install" | "uninstall" | "update".
	pending: { type: String, default: "" },
	error: { type: String, default: "" },
});

defineEmits(["install", "uninstall", "update"]);

const busy = computed(() => Boolean(props.pending));
const imageFailed = ref(false);
const initial = computed(() => (props.app.title || "?").charAt(0));

const incompatibleReason = computed(() =>
	props.app.required_version
		? __("Requires Frappe {0}", [props.app.required_version])
		: __("Not available for this version of Frappe")
);
</script>
