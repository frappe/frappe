<!--
  A Link or Dynamic Link cell's text: a link to the record it names, as the record's read-only field
  draws it. The row is a link too: a plain click opens this record, not the row's.
-->
<template>
	<RecordAnchor
		v-if="record.href.value"
		:href="record.href.value"
		:title="__('Open {0}', [text])"
		class="underline-offset-2 hover:underline"
		@open="record.open"
	>
		{{ text }}
	</RecordAnchor>
	<template v-else>{{ text }}</template>
</template>

<script setup lang="ts">
import { useRecordLink } from "@framework/ui/fields";
import { RecordAnchor } from "@framework/ui/Link";
import { __ } from "@/i18n";

const props = defineProps<{ doctype: string; name: string; text: string }>();

const record = useRecordLink(
	() => props.doctype,
	() => props.name
);
</script>
