<!-- The collapsed band: the comment control, and the `+` menu of what the strip's tabs create. -->
<template>
	<div
		class="pointer-events-auto flex items-center gap-1 rounded-6 bg-surface-elevation-2 py-1.5 pl-2 pr-1.5 shadow-md"
		data-composer-pill
	>
		<button
			v-if="comment"
			type="button"
			class="flex min-w-0 flex-1 items-center gap-2 text-left text-base text-ink-gray-5"
			data-composer-comment
			@click="emit('open', comment.name)"
		>
			<Avatar
				:label="user.full_name || user.name"
				:image="user.user_image ?? undefined"
				size="sm"
			/>
			<span class="truncate">{{ __("Add a comment…") }}</span>
		</button>

		<Dropdown v-if="creates.length" :options="creates" side="top" align="end">
			<!-- The trigger must own a box: Tooltip drops the attrs the menu anchors on. -->
			<div class="flex shrink-0" :class="{ 'ml-auto': !comment }" data-composer-create>
				<Tooltip :text="__('Add to this record')" placement="top">
					<Button icon="lucide-plus" variant="ghost" :label="__('Add to this record')" />
				</Tooltip>
			</div>
		</Dropdown>
	</div>
</template>

<script setup lang="ts">
import { Avatar, Button, Dropdown, Tooltip } from "frappe-ui";
import type { SessionUser } from "@framework/ui/api";
import type { WriterItem } from "@/recordPage/types";
import { __ } from "@/i18n";
import type { CreateOption } from "./createMenu";

defineProps<{
	/** The `comment` writer while it is on the list. */
	comment?: WriterItem;
	creates: CreateOption[];
	user: SessionUser;
}>();

const emit = defineEmits<{ open: [name: string] }>();
</script>
