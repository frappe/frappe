<!--
  The About dialog at `#about`: the app you are in first, then Frappe Framework and the other
  installed apps, each with a copy button for a bug report.
-->
<template>
	<Dialog
		:modelValue="open"
		:title="__('About')"
		size="md"
		@update:modelValue="(value: boolean) => value || emit('close')"
	>
		<p v-if="failure !== null" class="text-sm text-ink-red-4">
			{{ __("Could not load the installed apps: {0}", [failure]) }}
		</p>

		<div v-else-if="!versions" aria-hidden="true" class="flex flex-col gap-4">
			<Skeleton class="h-14 w-full rounded-4" />
			<Skeleton class="h-24 w-full rounded-4" />
		</div>

		<div v-else class="flex flex-col gap-5" data-testid="about">
			<section v-if="header" class="flex items-center gap-3" data-about-header>
				<AppLogo :logo="header.logo" :title="header.title" :size="56" />
				<div class="min-w-0 flex-1">
					<h3 class="text-lg font-semibold text-ink-gray-9">{{ __(header.title) }}</h3>
					<p v-if="header.description" class="text-sm text-ink-gray-5">
						{{ __(header.description) }}
					</p>
					<p class="text-sm text-ink-gray-6">
						{{ header.name }}: {{ versionText(header) }}
					</p>
				</div>
				<Button v-if="updatable(header)" v-bind="UPDATE" />
			</section>

			<div class="-ml-2 flex items-center gap-1" data-about-links>
				<Button
					v-for="link in LINKS"
					:key="link.href"
					variant="ghost"
					:icon-left="link.icon"
					:label="link.label"
					:href="link.href"
				/>
			</div>

			<!-- Out by the row's own padding, so its text sits on the dialog's content edge. -->
			<div v-if="boot.is_fc_site" class="-mx-2.5">
				<ItemListRow
					as="a"
					href="https://frappecloud.com/support"
					target="_blank"
					rel="noopener noreferrer"
					size="md"
					data-about-support
				>
					<template #label>
						<span class="block text-base text-ink-gray-8">{{
							__("Frappe Support")
						}}</span>
						<span class="block text-sm text-ink-gray-5">{{
							__("Visit Frappe Support Portal")
						}}</span>
					</template>
					<template #suffix>
						<span
							class="lucide-external-link mr-2 size-4 text-ink-gray-5"
							aria-hidden="true"
						/>
					</template>
				</ItemListRow>
			</div>

			<section class="flex flex-col gap-1">
				<div class="flex items-center justify-between">
					<h4 class="text-xs font-medium uppercase text-ink-gray-6">
						{{ __("Installed apps") }}
					</h4>
					<Button
						variant="ghost"
						icon-left="lucide-clipboard"
						:label="__('Copy all versions')"
						@click="copy(allVersionsBlock(versions))"
					/>
				</div>

				<!-- Out by the row's own padding, so a row's logo and version sit on the section's edges. -->
				<ul class="-mx-3 flex flex-col" data-about-apps>
					<li v-for="app in apps" :key="app.name" :data-key="app.name">
						<ItemListRow
							size="lg"
							class="group/row hover:bg-surface-gray-2 has-[:focus-visible]:bg-surface-gray-2"
						>
							<template #prefix>
								<AppLogo :logo="app.logo" :title="app.title" :size="20" />
							</template>
							<template #label>
								<span class="block truncate text-base text-ink-gray-8">{{
									__(app.title)
								}}</span>
								<span
									v-if="app.description"
									class="block truncate text-sm text-ink-gray-5"
									:title="__(app.description)"
									>{{ __(app.description) }}</span
								>
							</template>
							<template #suffix>
								<Button v-if="updatable(app)" v-bind="UPDATE" />
								<!-- One grid cell holds both, so the slot keeps the wider and nothing shifts. -->
								<button
									type="button"
									class="group/copy mr-2 grid cursor-pointer justify-items-end rounded-3 outline-none focus-visible:focus-ring"
									:aria-label="
										__('Copy {0} version {1}', [app.title, versionText(app)])
									"
									@click="copy(appLine(app.name, app))"
								>
									<span
										class="col-start-1 row-start-1 text-sm text-ink-gray-6 group-hover/row:invisible group-focus-visible/copy:invisible"
										>{{ versionText(app) }}</span
									>
									<span
										class="lucide-copy invisible col-start-1 row-start-1 size-4 text-ink-gray-6 group-hover/row:visible group-focus-visible/copy:visible"
										aria-hidden="true"
									/>
								</button>
							</template>
						</ItemListRow>
					</li>
				</ul>
			</section>

			<p class="text-center text-sm text-ink-gray-4">
				{{ __("© Frappe Technologies Pvt. Ltd. and contributors") }}
			</p>
		</div>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from "vue";
import { Button, Dialog, ItemListRow, Skeleton, toast } from "frappe-ui";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import {
	allVersionsBlock,
	appLine,
	headerApp,
	listedApps,
	loadVersions,
	versionText,
	type AboutApp,
	type AppVersions,
} from "./about";
import AppLogo from "./AppLogo.vue";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();

const boot = inject<Boot>("boot")!;

const LINKS = [
	{ label: __("Website"), icon: "lucide-globe", href: "https://frappe.io/" },
	{ label: __("Source code"), icon: "lucide-code-xml", href: "https://github.com/frappe" },
	{ label: __("Forum"), icon: "lucide-message-circle", href: "https://discuss.frappe.io" },
];

const UPDATE = {
	label: __("Update Available"),
	href: `https://frappecloud.com/dashboard/sites/${window.location.hostname}`,
};

const versions = ref<AppVersions | null>(null);
const failure = ref<string | null>(null);

const header = computed(() => versions.value && headerApp(versions.value, boot.app));
const apps = computed(() =>
	versions.value ? listedApps(versions.value, header.value?.name) : []
);

// Fetched on the first open, then kept.
watch(
	() => props.open,
	(isOpen) => isOpen && !versions.value && load(),
	{ immediate: true }
);

async function load() {
	failure.value = null;
	try {
		versions.value = await loadVersions();
	} catch (error) {
		failure.value = error instanceof Error ? error.message : String(error);
	}
}

/** Updates are for the framework, and only a Frappe Cloud site can take them. */
function updatable(app: AboutApp) {
	return app.name === "frappe" && boot.is_fc_site && boot.has_app_updates;
}

async function copy(text: string) {
	try {
		await navigator.clipboard.writeText(text);
	} catch {
		toast.error(__("Could not copy"));
		return;
	}
	toast.success(__("Copied"));
}
</script>
