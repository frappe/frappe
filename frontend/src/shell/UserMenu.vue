<!-- The avatar menu: the person's profile, the shell's acts for them and the page's own rows. The rail and the index draw it. -->
<template>
	<Dropdown
		:options="menu"
		:side="wide || tab ? 'top' : awaySide()"
		:align="wide ? 'start' : 'end'"
	>
		<button
			v-if="tab"
			type="button"
			data-key="user-menu"
			:aria-label="__('You')"
			class="flex min-h-14 flex-col items-center justify-center gap-1 py-2 transition active:scale-95"
		>
			<Avatar
				:image="boot.session.user.user_image"
				:label="boot.session.user.full_name"
				size="md"
			/>
			<span class="text-xs-medium leading-tighter text-ink-gray-5">{{ __("You") }}</span>
		</button>
		<button v-else-if="wide" type="button" data-key="user-menu" :class="WIDE_ROW">
			<Avatar
				:image="boot.session.user.user_image"
				:label="boot.session.user.full_name"
				size="md"
			/>
			<span class="truncate text-sm text-ink-gray-8">{{ boot.session.user.full_name }}</span>
		</button>
		<button
			v-else
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
import { __ } from "@/i18n";
import type { Boot } from "@/boot";
import { awaySide } from "./navigationSide";
import { pageMenuItems } from "./pageMenu";
import { colorSchemes, shellAct, shellMenu } from "./shellActs";

defineProps<{ wide?: boolean; tab?: boolean }>();

const WIDE_ROW =
	"flex h-8 w-full min-w-0 items-center gap-2 rounded-4 px-2 text-left transition hover:bg-surface-gray-3 focus-visible:ring-0 focus-visible:focus-ring";
const USER_CELL =
	"flex rounded-full transition hover:opacity-90 focus-visible:ring-0 focus-visible:focus-ring";

const boot = inject<Boot>("boot")!;

const { colorScheme } = useColorScheme();

const menu = computed<DropdownOptions>(() =>
	[
		[profileHeader()],
		[
			...shellMenu(["my_settings", "customize_sidebar"]),
			...themeRow(),
			...pageMenuItems.value,
		],
		shellMenu(["desk_v1"]),
		shellMenu(["log_out"]).map((option) => ({ ...option, theme: "red" as const })),
	]
		.filter((options) => options.length)
		.map((options) => ({ group: "", hideLabel: true, options }))
);

function themeRow() {
	const theme = shellAct("theme");
	if (!theme) return [];
	const submenu = colorSchemes().map((scheme) => ({
		label: scheme.label,
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
