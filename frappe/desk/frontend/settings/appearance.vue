<!-- The desk's colour scheme (light, dark or the system's, kept in this browser) and the person's navigation side. -->
<template>
	<SettingsRow :title="__('Theme')">
		<Select
			class="w-56"
			:model-value="colorScheme"
			:options="SCHEMES"
			@update:model-value="setColorScheme"
		/>
	</SettingsRow>
	<div data-fieldname="navigation_side">
		<SettingsRow :title="__('Navigation side')">
			<Skeleton v-if="user.loading" class="h-7 w-56 rounded-4" />
			<Select
				v-else
				class="w-56"
				:model-value="user.doc.navigation_side || ''"
				:options="sides"
				@update:model-value="pick"
			/>
		</SettingsRow>
		<ErrorMessage v-if="refused" class="-mt-1.5 pb-3.5" :message="refused" />
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import {
	ErrorMessage,
	Select,
	SettingsRow,
	Skeleton,
	useColorScheme,
	type ColorScheme,
} from "frappe-ui";
import { setOwnNavigationSide, sideLabel, siteNavigationSide } from "@shell";
import { __ } from "frappe/i18n";

/** The part of the settings dialog's binding this block reads; the full shape is `ComponentBinding`. */
interface Binding {
	readonly doc: Record<string, any>;
	readonly loading: boolean;
	readonly error: string;
	commit(): Promise<void>;
}

const props = defineProps<{ bindings: { user: Binding } }>();
const user = props.bindings.user;

const SCHEMES: { label: string; value: ColorScheme; icon: string }[] = [
	{ label: __("Light"), value: "light", icon: "lucide-sun" },
	{ label: __("Dark"), value: "dark", icon: "lucide-moon" },
	{ label: __("System"), value: "system", icon: "lucide-monitor" },
];

const { colorScheme, setColorScheme } = useColorScheme();

const sides = computed(() => [
	{ label: __("Site default ({0})", [sideLabel(siteNavigationSide.value)]), value: "" },
	{ label: sideLabel("start"), value: "start" },
	{ label: sideLabel("end"), value: "end" },
]);

const refused = ref("");

/** The shell redraws only once the save is accepted, with the value the binding settled on; a refusal shows under the row. */
async function pick(value: string) {
	user.doc.navigation_side = value;
	await user.commit();
	refused.value = user.error;
	if (!refused.value) setOwnNavigationSide(user.doc.navigation_side || "");
}
</script>
