<!-- The avatar menu: the person's profile, settings, theme, desk v1 and log out. The rail and the index draw it. -->
<template>
	<Dropdown :options="menu" side="right" align="end">
		<button
			type="button"
			data-key="user-menu"
			:class="USER_CELL"
			:aria-label="boot.session.user.full_name"
		>
			<Avatar
				:image="boot.session.user.user_image"
				:label="boot.session.user.full_name"
				size="lg"
			/>
		</button>
	</Dropdown>

	<LogoutDialog v-model="confirmingLogout" />
</template>

<script setup lang="ts">
import { computed, h, inject, ref } from "vue";
import { Avatar, Dropdown, useColorScheme, type DropdownOptions } from "frappe-ui";
import type { Boot } from "@/boot";
import LogoutDialog from "./LogoutDialog.vue";
import { OpenSettingsKey } from "./openSettings";

const USER_CELL =
	"flex rounded-full transition hover:opacity-90 focus-visible:ring-0 focus-visible:focus-ring";

const boot = inject<Boot>("boot")!;
const openSettings = inject(OpenSettingsKey)!;

const { colorScheme, setColorScheme } = useColorScheme();
const SCHEMES = [
	{ label: "Light", value: "light", icon: "lucide-sun" },
	{ label: "Dark", value: "dark", icon: "lucide-moon" },
	{ label: "System", value: "system", icon: "lucide-monitor" },
] as const;

const confirmingLogout = ref(false);

const menu = computed<DropdownOptions>(() => [
	{ group: "", hideLabel: true, options: [profileHeader()] },
	{
		group: "",
		hideLabel: true,
		options: [
			{
				label: "My settings",
				icon: "lucide-circle-user",
				onClick: () => openSettings("desk", "profile"),
			},
			{
				label: "Theme",
				icon: "lucide-sun-moon",
				submenu: SCHEMES.map((scheme) => ({
					label: scheme.label,
					icon: scheme.icon,
					selected: colorScheme.value === scheme.value,
					onClick: () => setColorScheme(scheme.value),
				})),
			},
		],
	},
	{
		group: "",
		hideLabel: true,
		options: [
			{ label: "Desk v1", icon: "lucide-arrow-left-right", onClick: () => leave("/app") },
		],
	},
	{
		group: "",
		hideLabel: true,
		options: [
			{
				label: "Log out",
				icon: "lucide-log-out",
				theme: "red",
				onClick: () => (confirmingLogout.value = true),
			},
		],
	},
]);

// A disabled row cannot be selected; the inline cursor beats the wrapper's `cursor-not-allowed`.
function profileHeader() {
	const { full_name, user_image, email } = boot.session.user;
	return {
		label: full_name,
		disabled: true,
		slots: {
			item: () =>
				h(
					"div",
					{
						"data-key": "profile",
						class: "flex items-center gap-2 px-2 py-1.5",
						style: { cursor: "default" },
					},
					[
						h(Avatar, { image: user_image, label: full_name, size: "xl" }),
						h("div", { class: "flex flex-col gap-0.5 min-w-0" }, [
							h(
								"div",
								{ class: "truncate text-sm font-semibold text-ink-gray-9" },
								full_name
							),
							h("div", { class: "truncate text-xs text-ink-gray-5" }, email),
						]),
					]
				),
		},
	};
}

function leave(href: string) {
	window.location.assign(href);
}
</script>
