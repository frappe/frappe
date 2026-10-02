<script setup>
import { onMounted } from "vue";

// Raven's mobile profile (apps/mobile/app/[site_id]/(tabs)/profile), in its own Tailwind with
// its colour tokens swapped for frappe-ui's:
//   screen        (card)                       -> bg-surface-gray-1
//   row           (bg-background dark:bg-card) -> bg-surface-elevation-2
//   muted text    (text-muted-foreground/80)   -> text-ink-gray-5
//   destructive   (text-destructive)           -> text-ink-red-5
//   border        (border-border)              -> border-outline-gray-2
// and its radii as values: frappe-ui's preset replaces Tailwind's rounded-xl and -2xl.

defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["title", "actions"]);

const frappe = window.frappe;
const __ = window.__;

const user = frappe.user_info(frappe.session.user);
const initials = (user.fullname || frappe.session.user)
	.split(" ")
	.slice(0, 2)
	.map((word) => word[0])
	.join("")
	.toUpperCase();

const THEMES = { light: __("Light"), dark: __("Dark"), automatic: __("Automatic") };
const theme = THEMES[document.documentElement.getAttribute("data-theme-mode")] || THEMES.light;

function open_settings(id) {
	// Not in the desk bundle, so it is loaded on tap, as the sidebar's Settings row does.
	frappe.require("user_settings_dialog.bundle.js").then(() => frappe.ui.show_user_settings(id));
}

// Rows with a value show it; the rest lead somewhere and show a chevron. Each one opens a
// section of the settings dialog (frappe.ui.show_user_settings). Keyboard Shortcuts is left
// out: a phone has no keyboard to set them for.
const PERSONAL = [
	{ id: "profile", label: __("Name"), icon: "user", value: user.fullname },
	{ id: "email", label: __("Email"), icon: "mail", value: frappe.session.user_email },
];
const PREFERENCES = [
	{ id: "appearance", label: __("Appearance"), icon: "palette", value: theme },
	{ id: "preferences", label: __("Preferences"), icon: "settings" },
	{ id: "lists", label: __("Lists"), icon: "list" },
	{ id: "forms", label: __("Forms"), icon: "file" },
	{ id: "reports", label: __("Reports"), icon: "table" },
	{ id: "session-defaults", label: __("Session Defaults"), icon: "sliders-horizontal" },
];

// The rest of the sidebar's user menu. Settings is the rows above, the dock is not on a
// phone to manage, and Logout gets the card at the end.
const menu = (frappe.app.sidebar?.user_menu_options() || []).flatMap((group) => group.options);
const logout = menu.find((option) => option.name === "logout");
const MORE = menu.filter(
	(option) =>
		!["settings", "workspace-selector", "logout"].includes(option.name) &&
		(!option.condition || option.condition())
);

function open(option) {
	if (option.href) frappe.set_route(option.href);
	else option.onclick?.();
}

const version = frappe.boot.versions?.frappe;

onMounted(() => {
	// A phone's page. A wider screen has the sidebar's user menu, and the User form for
	// the profile itself, so it goes there instead. The route is replaced so Back does not
	// land here again.
	if (!frappe.is_mobile()) {
		frappe.route_flags.replace_route = true;
		frappe.set_route("Form", "User", frappe.session.user);
		return;
	}

	emit("title", __("Profile"));
	emit("actions", []);
});

// Desk names its icons by their lucide names. Written out whole, so Tailwind's scan finds
// every class.
const ICONS = {
	user: "lucide-user",
	mail: "lucide-mail",
	palette: "lucide-palette",
	settings: "lucide-settings",
	list: "lucide-list",
	file: "lucide-file",
	table: "lucide-table",
	"sliders-horizontal": "lucide-sliders-horizontal",
	"rotate-ccw": "lucide-rotate-ccw",
};
</script>

<template>
	<div class="h-full overflow-y-auto bg-surface-gray-1 px-4 pb-10">
		<div class="mt-1.5 flex flex-col gap-4">
			<div class="items-center py-3">
				<img
					v-if="user.image"
					:src="user.image"
					:alt="user.fullname"
					class="mx-auto h-40 w-40 rounded-[16px] object-cover"
				/>
				<div
					v-else
					class="mx-auto flex h-40 w-40 items-center justify-center rounded-[16px] border border-outline-gray-2 bg-surface-elevation-2 text-5xl text-ink-gray-7"
				>
					{{ initials }}
				</div>
			</div>

			<div class="flex flex-col gap-0.5">
				<p class="pl-2 pb-1 text-xs text-ink-gray-5">{{ __("Personal Info") }}</p>
				<button
					v-for="row in PERSONAL"
					:key="row.id"
					type="button"
					class="flex flex-row items-center justify-between gap-3 rounded-[12px] bg-surface-elevation-2 py-2.5 px-4 active:bg-surface-gray-2"
					@click="open_settings(row.id)"
				>
					<span class="flex shrink-0 flex-row items-center gap-2">
						<span :class="ICONS[row.icon]" class="size-[18px] text-ink-gray-6" />
						<span class="text-base text-ink-gray-9">{{ row.label }}</span>
					</span>
					<span class="truncate text-base text-ink-gray-9">{{ row.value }}</span>
				</button>
			</div>

			<div class="flex flex-col gap-0.5">
				<p class="pl-2 pb-1 text-xs text-ink-gray-5">{{ __("Preferences") }}</p>
				<button
					v-for="row in PREFERENCES"
					:key="row.id"
					type="button"
					class="flex flex-row items-center justify-between rounded-[12px] bg-surface-elevation-2 py-0 pl-4 pr-2 active:bg-surface-gray-2"
					@click="open_settings(row.id)"
				>
					<span class="flex flex-row items-center gap-2 py-2.5">
						<span :class="ICONS[row.icon]" class="size-[18px] text-ink-gray-6" />
						<span class="text-base text-ink-gray-9">{{ row.label }}</span>
					</span>
					<span v-if="row.value" class="pr-2 text-base text-ink-gray-5">{{
						row.value
					}}</span>
					<span v-else class="flex h-10 flex-row items-center">
						<span class="lucide-chevron-right size-[22px] text-ink-gray-4" />
					</span>
				</button>
			</div>

			<div v-if="MORE.length" class="flex flex-col gap-0.5">
				<button
					v-for="option in MORE"
					:key="option.name"
					type="button"
					class="flex flex-row items-center justify-between rounded-[12px] bg-surface-elevation-2 py-0 pl-4 pr-2 active:bg-surface-gray-2"
					@click="open(option)"
				>
					<span class="flex flex-row items-center gap-2 py-2.5">
						<span
							:class="ICONS[option.icon] || 'lucide-circle-dot'"
							class="size-[18px] text-ink-gray-6"
						/>
						<span class="text-base text-ink-gray-9">{{ option.label }}</span>
					</span>
					<span class="flex h-10 flex-row items-center">
						<span class="lucide-chevron-right size-[22px] text-ink-gray-4" />
					</span>
				</button>
			</div>

			<button
				v-if="logout"
				type="button"
				class="flex flex-row items-center justify-between rounded-[12px] bg-surface-elevation-2 py-3 px-4 active:bg-surface-red-1"
				@click="open(logout)"
			>
				<span class="font-medium text-ink-red-5">{{ __("Log Out") }}</span>
				<span class="lucide-log-out size-4 text-ink-gray-4" />
			</button>

			<div class="flex flex-col items-center justify-center gap-1 pt-2">
				<p class="text-lg text-ink-gray-5">frappe</p>
				<p v-if="version" class="text-xs text-ink-gray-5">
					{{ __("Version {0}", [version]) }}
				</p>
			</div>
		</div>
	</div>
</template>
