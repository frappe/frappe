<!-- The site's navigation side. A component and not a generated row, which would show the raw start/end. -->
<template>
	<div data-fieldname="navigation_side">
		<SettingsRow :title="__('Navigation side')">
			<Skeleton v-if="site.loading" class="h-7 w-56 rounded-4" />
			<Select
				v-else
				class="w-56"
				:model-value="site.doc.navigation_side || 'start'"
				:options="sides"
				@update:model-value="pick"
			/>
		</SettingsRow>
		<ErrorMessage v-if="refused" class="-mt-1.5 pb-3.5" :message="refused" />
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { ErrorMessage, Select, SettingsRow, Skeleton } from "frappe-ui";
import { setSiteNavigationSide, sideLabel } from "@shell";
import { __ } from "frappe/i18n";

/** The part of the settings dialog's binding this block reads; the full shape is `ComponentBinding`. */
interface Binding {
	readonly doc: Record<string, any>;
	readonly loading: boolean;
	readonly error: string;
	commit(): Promise<void>;
}

const props = defineProps<{ bindings: { site: Binding } }>();
const site = props.bindings.site;

const sides = [
	{ label: sideLabel("start"), value: "start" },
	{ label: sideLabel("end"), value: "end" },
];

const refused = ref("");

/** A person with no side of their own follows the site, so the shell redraws once the save is accepted. */
async function pick(value: string) {
	site.doc.navigation_side = value;
	await site.commit();
	refused.value = site.error;
	if (!refused.value) setSiteNavigationSide(value);
}
</script>
