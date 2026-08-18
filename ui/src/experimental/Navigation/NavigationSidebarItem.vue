<template>
	<SidebarItem :label="item.label" :to="to" :active="isActive" :onClick="follow">
		<template #prefix>
			<ViewIcon :icon="item.icon" />
		</template>

		<template #suffix>
			<div class="relative mr-1 flex min-w-7 shrink-0 items-center justify-end gap-1 pr-1">
				<Icon
					v-if="isStoredDefault"
					name="star"
					class="size-3 shrink-0 text-ink-gray-4 transition-opacity"
					:class="fadeOnHover"
					:aria-label="`${item.label} is the default view`"
				/>
				<span
					v-if="hasCount"
					class="text-xs tabular-nums text-ink-gray-5 transition-opacity"
					:class="fadeOnHover"
				>
					{{ count }}
				</span>
				<Dropdown
					v-if="actions.length"
					v-model:open="isMenuOpen"
					:options="options"
					align="start"
					side="right"
				>
					<Button
						variant="ghost"
						size="xs"
						icon="lucide-more-horizontal text-ink-gray-5"
						:aria-label="`Actions for ${item.label}`"
						class="absolute right-0 -mr-0.5 opacity-0 transition-opacity group-hover/sidebar-item:opacity-100 group-focus-within/sidebar-item:opacity-100"
						:class="{ 'opacity-100': isMenuOpen }"
						@click.stop.prevent
					/>
				</Dropdown>
			</div>
		</template>
	</SidebarItem>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Button, Dropdown, SidebarItem } from "frappe-ui";
import { Icon } from "frappe-ui/icons";
import { ViewIcon, getViewActions } from "../SavedViews";
import { itemTarget } from "./items";
import type { ViewAction, ViewActionKind } from "../SavedViews";
import type { NavigationItem } from "./types";

const props = defineProps<{
	item: NavigationItem;
	to: string;
	isActive: boolean;
	canManageShared: boolean;
	count?: number | null;
	isStoredDefault?: boolean;
}>();

const emit = defineEmits<{ act: [kind: ViewActionKind, item: NavigationItem] }>();

const isMenuOpen = ref(false);

const target = computed(() => (props.item.view ? { path: props.to } : itemTarget(props.item)));
const to = computed(() => ("path" in target.value ? target.value.path : undefined));

function follow() {
	if (!("leave" in target.value)) return;
	if (props.item.new_tab) window.open(target.value.leave, "_blank", "noopener");
	else window.location.assign(target.value.leave);
}

const actions = computed(() =>
	props.item.view
		? getViewActions(props.item.view, props.canManageShared, props.isStoredDefault)
		: []
);

const hasCount = computed(() => props.count != null && props.count > 0);

const fadeOnHover = computed(() => [
	actions.value.length &&
		"group-hover/sidebar-item:opacity-0 group-focus-within/sidebar-item:opacity-0",
	{ "opacity-0": isMenuOpen.value },
]);

const options = computed(() =>
	actions.value.map((action: ViewAction) => ({
		label: action.label,
		icon: action.icon,
		theme: action.danger ? ("red" as const) : undefined,
		onClick: (event: PointerEvent) => {
			event?.stopPropagation?.();
			emit("act", action.kind, props.item);
		},
	}))
);
</script>
