<script setup>
import { computed, onUnmounted, reactive, ref, watch } from "vue";
import { Button, Switch, TextInput } from "frappe-ui";
import { on_phone_visit } from "../search/phone_page.js";
import Group from "./components/Group.vue";
import Photo from "./components/Photo.vue";
import Row from "./components/Row.vue";

// Gameplan's phone "You" page (frontend/src/components/MobileMoreMenu.vue) and its settings
// pages: the avatar and name, then grouped rows, with the settings tabs listed directly.
// Gameplan's "Profile" settings tab is "Personal Info" here, since the page is Profile.

const props = defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["title", "actions"]);

const frappe = window.frappe;
const __ = window.__;
const me = frappe.session.user;

// Each settings section is a screen below the profile: /desk/profile/preferences. The
// fields, the values and the saving all come from the settings dialog's own module
// (frappe.ui.user_settings), so a section reads and saves the same on either.
const SCREENS = {
	personal: __("Personal Info"),
	email: __("Email"),
	preferences: __("Preferences"),
	lists: __("Lists"),
	forms: __("Forms"),
	reports: __("Reports"),
	"session-defaults": __("Session Defaults"),
};
const screen = computed(() => (SCREENS[props.route[0]] ? props.route[0] : null));
const go = (...route) => frappe.set_route("profile", ...route);

const settings = ref(null);
const user_data = reactive({});
const language = ref("");

// the user_info desk keeps, which a save of the name or the photo updates
const user = ref(frappe.user_info(me));
const refresh_user = () => (user.value = { ...frappe.user_info(me) });

// Bumped when the page is hidden, so a load still running from an earlier visit writes nothing
let load_id = 0;

// Everything is written at the end, `settings` last: the controls show once it is set, and an
// edit made before the saved values arrived would be overwritten by them.
async function load() {
	const id = load_id;
	// Not in the desk bundle, so it is loaded the first time the page shows.
	await frappe.require("user_settings_dialog.bundle.js");
	const user_settings = frappe.ui.user_settings;
	const values = await user_settings.load();
	// only the display name; the code stands in if the lookup fails
	const language_name = await Promise.resolve(
		user_settings.language_name(values.language)
	).catch(() => values.language);
	if (id !== load_id) return;

	Object.assign(user_data, values);
	language.value = language_name;
	Object.assign(name_form, pick_name(values));
	settings.value = user_settings;
}

const switches = (section) => settings.value?.switches(section) || [];

function toggle(fieldname, on) {
	const before = user_data[fieldname];
	user_data[fieldname] = on ? 1 : 0;
	settings.value.save(fieldname, user_data[fieldname]).catch(() => {
		user_data[fieldname] = before;
	});
}

const pick_name = (data) => ({
	first_name: data.first_name || "",
	middle_name: data.middle_name || "",
	last_name: data.last_name || "",
	username: data.username || "",
});
const name_form = reactive(pick_name({}));
const saving = ref(false);
const name_changed = computed(() =>
	Object.keys(name_form).some((key) => name_form[key] !== (user_data[key] || ""))
);

function save_name() {
	saving.value = true;
	// a native promise: frappe.call's jQuery one has no finally
	Promise.resolve(settings.value.save_profile(user_data, name_form))
		.then(refresh_user)
		.finally(() => (saving.value = false));
}

function change(fieldname, after) {
	settings.value.change(fieldname, user_data, (value) => {
		user_data[fieldname] = value;
		after?.(value);
	});
}

function change_language() {
	change("language", (code) =>
		settings.value.language_name(code).then((name) => (language.value = name))
	);
}

// Gameplan's Theme row: a tap moves to the next theme, in this order.
const THEMES = {
	light: { label: __("Light"), value: "Light", icon: "lucide-sun" },
	dark: { label: __("Dark"), value: "Dark", icon: "lucide-moon" },
	automatic: { label: __("Automatic"), value: "Automatic", icon: "lucide-monitor-smartphone" },
};
const THEME_CYCLE = Object.keys(THEMES);
const theme_mode = ref(document.documentElement.getAttribute("data-theme-mode") || "light");

// Each tap shows its theme at once; only where the taps stop is saved. A save per tap could
// reach the server out of order and keep a theme that is no longer on screen.
let theme_save;
function cycle_theme() {
	const next = THEME_CYCLE[(THEME_CYCLE.indexOf(theme_mode.value) + 1) % THEME_CYCLE.length];
	theme_mode.value = next;
	document.documentElement.setAttribute("data-theme-mode", next);
	clearTimeout(theme_save);
	theme_save = setTimeout(
		() =>
			frappe.xcall("frappe.core.doctype.user.user.switch_theme", {
				theme: THEMES[next].value,
			}),
		600
	);
}

const session_defaults = frappe.boot.session_defaults || [];
const can_configure_defaults = frappe.model.can_read("Session Default Settings");

// The settings tabs, listed directly as Gameplan lists its own.
const SETTINGS_ROWS = [
	{ screen: "personal", icon: "lucide-user" },
	{ screen: "email", icon: "lucide-mail" },
	{ screen: "preferences", icon: "lucide-sliders-horizontal" },
	{ screen: "lists", icon: "lucide-list" },
	{ screen: "forms", icon: "lucide-file-text" },
	{ screen: "reports", icon: "lucide-table" },
	{ screen: "session-defaults", icon: "lucide-settings-2" },
];

// The sidebar user menu options this page does not list in its first group. Settings is
// the rows above, the dock is not on a phone to manage, Reload is not a thing a phone user
// reaches for, and Logout closes the Settings group.
const MENU_NOT_LISTED = ["settings", "workspace-selector", "reload", "logout"];
const menu = (frappe.app.sidebar?.user_menu_options() || []).flatMap((group) => group.options);
const logout = menu.find((option) => option.name === "logout");
const MORE = menu.filter(
	(option) => !MENU_NOT_LISTED.includes(option.name) && (!option.condition || option.condition())
);
const MENU_ICONS = { "my-space": "lucide-lock" };

function open(option) {
	if (option.href) frappe.set_route(option.href);
	else option.onclick?.();
}

// a screen change below the page is a new route too, and must not load the values again
let loading;

// Desk keeps this page mounted while another one shows, and the User form there can change
// these values, so a return loads them again. The controls wait for that load as they do
// for the first.
const wrapper = window.$(frappe.pages["profile"]);
const forget_values = () => {
	load_id++;
	loading = null;
	settings.value = null;
};
wrapper.on("hide", forget_values);
onUnmounted(() => wrapper.off("hide", forget_values));

on_phone_visit(props, ["Form", "User", me], () => {
	// No header on a phone, as Gameplan's page has none: the screens bring their own bar.
	// The same call the desktop page makes for its own header; it hides this page's only.
	frappe.pages["profile"]?.page?.page_head.hide();

	emit("actions", []);
	loading ||= load().catch(() => (loading = null));
});

watch(screen, (name) => emit("title", SCREENS[name] || __("Profile")), { immediate: true });
</script>

<template>
	<div class="h-full overflow-y-auto bg-surface-gray-1">
		<div v-if="screen" class="space-y-6 px-4 pt-3 pb-10">
			<!-- the page head is hidden (see onMounted), so a screen names itself -->
			<div class="flex items-center gap-1">
				<Button
					variant="ghost"
					size="lg"
					icon="lucide-chevron-left"
					:aria-label="__('Back to Profile')"
					@click="go()"
				/>
				<h1 class="truncate text-xl-semibold text-ink-gray-9">{{ SCREENS[screen] }}</h1>
			</div>

			<template v-if="screen === 'session-defaults'">
				<Group v-if="session_defaults.length" :label="__('Current values')">
					<Row
						v-for="(field, index) in session_defaults"
						:key="field.fieldname"
						icon="lucide-bookmark"
						:label="field.label"
						:value="field.default || __('Not set')"
						:divider="index > 0"
						@click="frappe.ui.toolbar.setup_session_defaults()"
					/>
				</Group>
				<p v-else class="pl-4 text-lg text-ink-gray-5">
					{{ __("No session defaults configured.") }}
				</p>
				<Group>
					<Row
						v-if="session_defaults.length"
						icon="lucide-pencil"
						:label="__('Edit')"
						@click="frappe.ui.toolbar.setup_session_defaults()"
					/>
					<Row
						v-if="can_configure_defaults"
						icon="lucide-settings"
						:label="__('Configure')"
						:divider="!!session_defaults.length"
						@click="frappe.set_route('Form', 'Session Default Settings')"
					/>
				</Group>
			</template>

			<Group v-else-if="!settings" aria-busy="true">
				<span class="sr-only">{{ __("Loading...") }}</span>
				<div v-for="index in 5" :key="index" class="flex min-h-14 items-center">
					<span class="flex w-14 shrink-0 justify-center">
						<span class="size-5 animate-pulse rounded bg-surface-gray-2" />
					</span>
					<span class="h-3 w-1/2 animate-pulse rounded bg-surface-gray-2" />
				</div>
			</Group>

			<template v-else-if="screen === 'personal'">
				<div class="flex flex-col items-center">
					<Photo :image="user.image" :name="user.fullname || me" />
					<Button
						variant="ghost"
						size="lg"
						class="mt-2"
						:label="__('Change photo')"
						@click="settings.upload_image(refresh_user)"
					/>
				</div>

				<section class="space-y-4 rounded-7 bg-surface-base p-4">
					<TextInput v-model="name_form.first_name" :label="__('First Name')" required />
					<TextInput v-model="name_form.middle_name" :label="__('Middle Name')" />
					<TextInput v-model="name_form.last_name" :label="__('Last Name')" />
					<TextInput v-model="name_form.username" :label="__('Username')" />
					<Button
						variant="solid"
						theme="gray"
						size="lg"
						class="w-full"
						:label="__('Save')"
						:loading="saving"
						:disabled="!name_changed || !name_form.first_name.trim()"
						@click="save_name"
					/>
				</section>

				<Group>
					<Row
						icon="lucide-key-round"
						:label="__('Change Password')"
						@click="frappe.ui.show_change_password_dialog(me)"
					/>
				</Group>
			</template>

			<!-- email, preferences, lists, forms and reports: switches, then their extra rows -->
			<template v-else>
				<Group>
					<div
						v-for="(field, index) in switches(screen)"
						:key="field.fieldname"
						class="relative px-4 py-3"
					>
						<span
							v-if="index > 0"
							class="pointer-events-none absolute left-4 right-4 top-0 border-t"
							aria-hidden="true"
						/>
						<Switch
							:label="field.label"
							:description="field.description"
							:model-value="!!user_data[field.fieldname]"
							@update:model-value="(on) => toggle(field.fieldname, on)"
						/>
					</div>
				</Group>

				<Group v-if="screen === 'email'" :label="__('Signature')">
					<Row
						icon="lucide-signature"
						:label="__('Email Signature')"
						:value="user_data.email_signature ? __('Set') : __('Not set')"
						@click="change('email_signature')"
					/>
				</Group>

				<Group v-if="screen === 'preferences'" :label="__('Locale')">
					<Row
						icon="lucide-languages"
						:label="__('Language')"
						:value="language"
						@click="change_language"
					/>
					<Row
						icon="lucide-globe"
						:label="__('Time Zone')"
						:value="user_data.time_zone || ''"
						divider
						@click="change('time_zone')"
					/>
				</Group>
			</template>
		</div>

		<div v-else class="px-4 pt-8 pb-10">
			<div class="flex flex-col items-center text-center">
				<Photo :image="user.image" :name="user.fullname || me" />
				<div class="mt-5 max-w-full truncate text-5xl-semibold text-ink-gray-9">
					{{ user.fullname }}
				</div>
				<Button
					variant="ghost"
					size="lg"
					class="mt-2"
					:label="__('View profile')"
					@click="frappe.set_route('Form', 'User', me)"
				/>
			</div>

			<div class="mt-8 space-y-6">
				<Group v-if="MORE.length">
					<Row
						v-for="(option, index) in MORE"
						:key="option.name"
						:icon="MENU_ICONS[option.name] || 'lucide-circle-dot'"
						:label="option.label"
						:divider="index > 0"
						@click="open(option)"
					/>
				</Group>

				<Group :label="__('Settings')">
					<Row
						v-for="(row, index) in SETTINGS_ROWS"
						:key="row.screen"
						:icon="row.icon"
						:label="SCREENS[row.screen]"
						:divider="index > 0"
						@click="go(row.screen)"
					/>
					<Row
						:icon="(THEMES[theme_mode] || THEMES.light).icon"
						:label="__('Theme')"
						:value="THEMES[theme_mode]?.label"
						divider
						@click="cycle_theme"
					/>
					<Row
						v-if="logout"
						icon="lucide-log-out"
						:label="__('Log out')"
						divider
						@click="open(logout)"
					/>
				</Group>
			</div>
		</div>
	</div>
</template>
