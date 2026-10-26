<!-- The avatar menu: the person's profile, the shell's acts for them and the page's own rows. The rail and the index draw it. -->
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
</template>

<script setup lang="ts">
import { computed, h, inject } from "vue";
import { Avatar, Dropdown, useColorScheme, type DropdownOptions } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { pageMenuItems } from "./pageMenu";
import { COLOR_SCHEMES, shellAct, shellMenu } from "./shellActs";

const USER_CELL =
	"flex rounded-full transition hover:opacity-90 focus-visible:ring-0 focus-visible:focus-ring";

const boot = inject<Boot>("boot")!;

const { colorScheme } = useColorScheme();

const menu = computed<DropdownOptions>(() =>
	[
		[profileHeader()],
		[...shellMenu(["my_settings"]), ...themeRow(), ...pageMenuItems.value],
		shellMenu(["desk_v1"]),
		shellMenu(["log_out"]).map((option) => ({ ...option, theme: "red" as const })),
	]
		.filter((options) => options.length)
		.map((options) => ({ group: "", hideLabel: true, options }))
);

function themeRow() {
	const theme = shellAct("theme");
	if (!theme) return [];
	const submenu = COLOR_SCHEMES.map((scheme) => ({
		label: __(scheme.label),
		icon: scheme.icon,
		selected: colorScheme.value === scheme.value,
		onClick: () => void acts.perform(theme.name, scheme.value),
	}));
	return [{ label: theme.label!, icon: theme.icon, submenu }];
}

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
</script>
