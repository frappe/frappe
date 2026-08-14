<template>
	<!-- The trail says where you are: the tool, the doctype it is scoped to, and
	     the script you have open (ticket 37). It is hand-rolled rather than
	     frappe-ui's `Breadcrumbs` for one structural reason — `Breadcrumbs`
	     renders its `#prefix`/`#suffix` slots *inside* each crumb's own
	     `<button>`, so hanging a picker there would nest one interactive element
	     in another, which is the exact defect the `SidebarItem` swap was made to
	     remove from the rail. What is given up is `Breadcrumbs`'
	     overflow-into-`⋯`, which three crumbs do not earn; the last crumb is
	     truncated by hand and the classes are copied so the two read the same. -->
	<div class="flex min-w-0 items-center">
		<!-- A static root: it has no parent to point at. Ticket 30 ruled out both
		     the cross-tier console and the standalone editor page, which is the
		     only thing an "all Page Scripts" crumb could open. It names the tool,
		     and the affordance stays unambiguous — the doctype crumb carries a
		     chevron, this carries nothing. -->
		<span
			class="flex shrink-0 items-center rounded px-0.5 py-1 text-lg-medium text-ink-gray-5"
		>
			Page Scripts
		</span>
		<span class="mx-0.5 shrink-0 text-base text-ink-gray-4" aria-hidden="true">/</span>

		<!-- The doctype is the one crumb you can change, so it is the one crumb
		     that is a control: `@framework/ui`'s own `Link` against `DocType`,
		     over `frappe.desk.search.search_link` (precedent: `DataImportList`).
		     `trigger="button"` keeps Combobox's search while letting the crumb
		     itself be the trigger — and because reka's `ComboboxAnchor` renders
		     `as-child`, the crumb *is* the anchor rather than a button inside
		     one. That is also why no click handler is wired here: the anchor
		     already forwards the toggle, and a second one would undo it.

		     The crumb reads `displayValue`, which is the option's server-side
		     label falling back to the value — never a title resolved here. -->
		<Link
			:modelValue="doctype"
			doctype="DocType"
			trigger="button"
			size="sm"
			placeholder="Switch doctype"
			@update:modelValue="onPick"
		>
			<template #trigger="{ open, displayValue }">
				<button
					type="button"
					class="flex shrink-0 items-center gap-1 rounded px-0.5 py-1 text-lg-medium transition"
					:class="open ? 'text-ink-gray-9' : 'text-ink-gray-5 hover:text-ink-gray-7'"
					:aria-label="`Doctype: ${displayValue || doctype}. Switch doctype`"
				>
					<span>{{ displayValue || doctype }}</span>
					<!-- A chevron *down*: this opens a menu below the crumb rather
					     than cycling values, so the up-down pair promised the wrong
					     gesture. -->
					<span class="lucide-chevron-down size-3 text-ink-gray-4" aria-hidden="true" />
				</button>
			</template>
		</Link>

		<!-- The third crumb exists only once a script is open: the empty state's
		     trail honestly stops at the doctype, because there is no script to be
		     in. This is not 23's deleted header row coming back — that row said
		     the script's name *and* its run position *and* its Enabled switch,
		     all of which the rail already said; this says the name once. -->
		<template v-if="script">
			<span class="mx-0.5 shrink-0 text-base text-ink-gray-4" aria-hidden="true">/</span>
			<span
				class="min-w-0 truncate rounded px-0.5 py-1 text-lg-medium text-ink-gray-9"
				:title="script"
			>
				{{ script }}
			</span>
		</template>
	</div>
</template>

<script setup lang="ts">
// The header's left zone: everything about *where* the author is. The state and
// the actions are the header's right-hand business (ticket 37, round 14).
import { Link } from "../../components/Link";

defineProps<{
	/** The doctype's name — the value, and what the URL and the stored `dt` carry. */
	doctype: string;
	/** The open script, absent in the empty state. */
	script?: string | null;
}>();

const emit = defineEmits<{
	"update:doctype": [doctype: string];
}>();

// `Link` clears to `null`, and there is no such thing as no doctype here — a
// clear is simply not a switch.
function onPick(value: string | null) {
	if (value) emit("update:doctype", value);
}
</script>
