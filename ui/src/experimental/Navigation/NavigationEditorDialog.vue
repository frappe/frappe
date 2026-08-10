<template>
	<Dialog v-model="open" size="sm" :title="title">
		<template #body-content>
			<NavigationSidebarEditor
				:navigation="navigation"
				:canManageShared="navigation.canManageShared.value"
				:itemKinds="itemKinds"
				:addOptions="addOptions"
				:flat="flat"
				@error="error = errorMessage($event)"
			/>
			<ErrorMessage class="mt-2" :message="error" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog, ErrorMessage } from "frappe-ui";
import NavigationSidebarEditor from "./NavigationSidebarEditor.vue";
import { errorMessage } from "../errorMessage";
import type { NavigationItemKind } from "./itemKinds";
import type { UseNavigation } from "./useNavigation";
import type { AddMenuOptions } from "./types";

withDefaults(
	defineProps<{
		navigation: UseNavigation;
		itemKinds?: NavigationItemKind[];
		addOptions?: (section: string | null) => AddMenuOptions;
		flat?: boolean;
		title?: string;
	}>(),
	{ title: "Customize sidebar" }
);

const open = defineModel<boolean>({ default: false });

const emit = defineEmits<{ open: [] }>();

const error = ref("");

watch(open, (isOpen) => {
	if (!isOpen) return;
	error.value = "";
	emit("open");
});
</script>
