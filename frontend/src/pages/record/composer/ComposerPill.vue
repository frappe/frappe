<!-- The collapsed band: Reply (Comment without the email writer), Comment, and the `+` menu. -->
<template>
	<div
		class="pointer-events-auto flex items-center gap-1 rounded-6 bg-surface-elevation-2 py-1.5 pl-2 pr-1.5 shadow-md"
		data-composer-pill
	>
		<button
			v-if="primary"
			type="button"
			class="flex min-w-0 flex-1 items-center gap-2 text-left text-base text-ink-gray-5"
			v-bind="{ [primary.mark]: '' }"
			@click="emit('open', primary.writer.name)"
		>
			<Avatar
				:label="user.full_name || user.name"
				:image="user.user_image ?? undefined"
				size="sm"
			/>
			<span class="truncate">{{ primary.text }}</span>
		</button>

		<Button
			v-if="email && comment"
			:icon="comment.icon || 'lucide-message-circle'"
			variant="ghost"
			size="xs"
			class="shrink-0"
			:label="__('Add a comment')"
			:tooltip="__('Add a comment')"
			data-composer-comment
			@click="emit('open', comment.name)"
		/>

		<Dropdown v-if="creates.length" :options="creates" side="top" align="end">
			<!-- The trigger must own a box: Tooltip drops the attrs the menu anchors on. -->
			<div class="flex shrink-0" :class="{ 'ml-auto': !primary }" data-composer-create>
				<Tooltip :text="__('Add to this record')" placement="top">
					<Button
						icon="lucide-plus"
						variant="ghost"
						size="xs"
						:label="__('Add to this record')"
					/>
				</Tooltip>
			</div>
		</Dropdown>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Avatar, Button, Dropdown, Tooltip } from "frappe-ui";
import type { SessionUser } from "@framework/ui/api";
import type { WriterItem } from "@/recordPage/types";
import { __ } from "@/i18n";
import type { CreateOption } from "./createMenu";

const props = defineProps<{
	/** The `comment` writer while it is on the list. */
	comment?: WriterItem;
	/** The `email` writer while it is on the list. */
	email?: WriterItem;
	creates: CreateOption[];
	user: SessionUser;
	/** The record's title as the header shows it. */
	title: string;
}>();

const emit = defineEmits<{ open: [name: string] }>();

const primary = computed(() => {
	if (props.email)
		return {
			writer: props.email,
			text: __("Reply to {0}", [props.title]),
			mark: "data-composer-reply",
		};
	if (props.comment)
		return {
			writer: props.comment,
			text: __("Add a comment…"),
			mark: "data-composer-comment",
		};
	return undefined;
});
</script>
