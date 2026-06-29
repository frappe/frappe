<template>
	<span class="text-ink-gray-5">
		<template v-for="(seg, i) in segments" :key="i">
			<span v-if="seg.bold" class="font-medium text-ink-gray-8">{{ seg.text }} </span>
			<template v-else>{{ seg.text }} </template>
		</template>
	</span>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { LogActivity } from "./types";

const props = defineProps<{ activity: LogActivity }>();

// Emphasise the actor (always available, any language) plus the assignee, which
// is parsed from the message via Frappe's English templates; other languages bold
// only the actor.
const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function mentions(text: string): string[] {
	const names = new Set<string>();
	const actor = props.activity.author?.fullname;
	if (actor) names.add(actor);

	// "Assignment of {assignee} removed by {actor}"
	const removed = text.match(/^Assignment of (.+?) removed by .+$/);
	if (removed) names.add(removed[1]);

	// "{actor} assigned {assignee}: {desc}" — anchored on actor so it skips "self assigned"
	if (actor) {
		const assigned = text.match(new RegExp("^" + escapeRegExp(actor) + " assigned (.+?): "));
		if (assigned) names.add(assigned[1]);
	}

	return [...names].filter(Boolean);
}

const segments = computed(() => {
	const text = props.activity.data.text ?? "";
	// match longest names first so "Foo Bar" wins over a stray "Foo"
	const names = mentions(text).sort((a, b) => b.length - a.length);
	if (!names.length) return [{ text, bold: false }];

	const re = new RegExp(`(${names.map(escapeRegExp).join("|")})`, "g");
	const nameSet = new Set(names);
	return text
		.split(re)
		.filter((p) => p !== "")
		.map((p) => ({ text: p, bold: nameSet.has(p) }));
});
</script>
