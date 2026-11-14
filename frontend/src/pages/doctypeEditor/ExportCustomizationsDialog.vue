<!-- Export customizations (developer mode): what desk v1's export asks. It closes with the answers. -->
<template>
	<div class="flex flex-col gap-5" data-export-dialog>
		<p class="text-p-base text-ink-gray-7">
			{{
				__(
					"Writes this site's changes to {0} into an app, so every site with the app gets them.",
					[doctype]
				)
			}}
		</p>
		<div class="flex flex-col gap-1.5" autofocus @focusin="caretAtEnd">
			<Combobox
				v-model="module"
				:label="__('Module')"
				:options="modules"
				:placeholder="__('Choose a module')"
			/>
			<p class="text-sm text-ink-gray-6" data-export-file>
				<template v-if="file">
					{{ __("Writes") }} <span class="font-mono text-ink-gray-7">{{ file }}</span>
				</template>
				<template v-else>{{ __("The app and the folder the file goes in.") }}</template>
			</p>
		</div>
		<div class="flex items-start justify-between gap-4">
			<div class="flex flex-col gap-0.5">
				<span class="text-base text-ink-gray-8">{{ __("Apply on migrate") }}</span>
				<span class="text-sm text-ink-gray-6">
					{{ __("Each migrate writes them to the site again.") }}
				</span>
			</div>
			<Switch v-model="sync" class="mt-0.5" />
		</div>
		<div class="flex items-start justify-between gap-4">
			<div class="flex flex-col gap-0.5">
				<span class="text-base text-ink-gray-8">{{ __("Include permissions") }}</span>
				<span class="text-sm text-ink-gray-6">
					{{ __("The roles this site added to {0}.", [doctype]) }}
				</span>
			</div>
			<Switch v-model="permissions" class="mt-0.5" />
		</div>
		<div class="flex items-center justify-between gap-3">
			<span class="text-sm text-ink-gray-6" data-export-changes>
				{{ resetLines(changes).join(", ") || __("No site changes yet") }}
			</span>
			<Button variant="solid" :label="__('Export')" :disabled="!module" @click="exportNow" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Button, Combobox, Switch } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { __ } from "@/i18n";
import { resetLines, type CustomizationCounts, type ExportAnswers } from "./customizeActs";
import { returnToMore } from "./returnToMore";

const props = defineProps<{
	doctype: string;
	/** The DocType's own module, picked first. */
	module: string;
	/** What this site changed: the rows the file carries. */
	changes: CustomizationCounts;
	close: (answers: ExportAnswers | null) => void;
}>();

returnToMore();

const module = ref<string | null>(props.module);
const apps = ref(new Map<string, string>());
const modules = computed(() => [...new Set([props.module, ...apps.value.keys()])]);
const sync = ref(true);
const permissions = ref(false);

// The combobox selects its text on focus; the caret goes after it instead.
function caretAtEnd({ target }: FocusEvent) {
	if (!(target instanceof HTMLInputElement)) return;
	const end = target.value.length;
	requestAnimationFrame(() => target.setSelectionRange(end, end));
}

onMounted(async () => {
	const { data } = await listDocuments<{ name: string; app_name: string }>("Module Def", {
		fields: ["name", "app_name"],
		order_by: "name asc",
		limit: 1000,
	});
	apps.value = new Map(data.map(({ name, app_name }) => [name, app_name]));
});

// The file goes in the module's app: <app>/<module>/custom/<doctype>.json.
const file = computed(() => {
	const app = module.value && apps.value.get(module.value);
	return app ? `${app}/${scrub(module.value!)}/custom/${scrub(props.doctype)}.json` : "";
});

// As frappe.utils.scrub: only spaces and hyphens become underscores.
function scrub(text: string) {
	return text.toLowerCase().replace(/[ -]/g, "_");
}

function exportNow() {
	props.close({
		module: module.value!,
		sync_on_migrate: sync.value,
		with_permissions: permissions.value,
	});
}
</script>
