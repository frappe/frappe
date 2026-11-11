<!-- One panel row: the label in a fixed column, the value in the flexible one. -->
<template>
	<div v-if="!hidden" class="grid grid-cols-[130px_1fr] items-start gap-2">
		<span class="h-7 truncate text-base leading-7 text-ink-gray-5" :title="field.label">
			{{ field.label }}
		</span>

		<div class="min-w-0">
			<FieldBox class="group" :interactive="interactive" :error="!!message">
				<div
					v-if="editing || inPlace"
					ref="cell"
					class="field min-w-0"
					:data-fieldname="field.fieldname"
					@focusout="onFocusout"
					@keydown.escape="cancel"
				>
					<!-- `ui.props` binds first so it cannot clobber `field` or `modelValue`; Vue merges
			     duplicate listeners, so `ui.on.change` and the close-on-commit both fire. -->
					<component
						:is="field.ui?.component ?? resolved"
						v-bind="controlProps"
						:field="controlField"
						:modelValue="doc[field.fieldname]"
						:error="drawsErrorText ? undefined : error"
						@update:modelValue="(value: any) => edit(field.fieldname, value)"
						@change="(value: any) => onCommit(value)"
						v-on="field.ui?.on ?? {}"
					/>
				</div>

				<div
					v-else
					class="flex min-h-7 min-w-0 flex-wrap items-center gap-x-1.5 px-2"
					:class="interactive ? 'cursor-pointer' : ''"
					:data-fieldname="field.fieldname"
					:role="imageUrl ? 'button' : undefined"
					:tabindex="imageUrl ? 0 : undefined"
					@click="open"
					@keydown.enter.self="open"
					@keydown.space.self.prevent="open"
				>
					<span
						class="flex min-w-0 flex-1 items-center text-base leading-7"
						:class="
							error
								? 'text-ink-red-6'
								: display
								? 'text-ink-gray-8'
								: 'text-ink-gray-4'
						"
					>
						<!-- An editable row's click opens its editor, so its address waits on the arrow. -->
						<a
							v-if="address?.kind === 'mail' && !interactive"
							:href="address.href"
							data-slot="mail-link"
							class="truncate underline-offset-2 hover:underline"
							@click.stop
							>{{ display }}</a
						>
						<template v-else-if="imageUrl">
							<img
								:src="imageUrl"
								alt=""
								class="me-2 size-5 shrink-0 rounded-2 object-cover"
							/>
							<span class="truncate text-ink-gray-8">{{ fileName(imageUrl) }}</span>
						</template>
						<template v-else>
							<LinkMark
								class="me-1.5"
								:source="field.linkMark"
								:value="mark"
								:text="display"
							/>
							<span
								v-if="secret > 0"
								class="truncate select-none [-webkit-text-security:disc]"
								>{{ "•".repeat(secret) }}</span
							>
							<span v-else class="truncate">{{ display || placeholder }}</span>
						</template>
					</span>
					<span
						v-if="summary"
						class="lucide-arrow-up-right ml-auto size-3.5 shrink-0 text-ink-gray-5"
						aria-hidden="true"
					/>
					<RecordAnchor
						v-else-if="record.href.value"
						:href="record.href.value"
						:aria-label="openLabel"
						:title="openLabel"
						class="lucide-arrow-up-right ml-auto size-3.5 shrink-0 text-ink-gray-5 opacity-0 hover:text-ink-gray-7 focus-visible:opacity-100 group-hover:opacity-100"
						@open="record.open"
					/>
					<DataOpenLink
						v-else-if="
							address && (address.kind === 'web' || (interactive && !composerEmail))
						"
						:address="address"
						class="ml-auto grid shrink-0 opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
					/>
					<span
						v-if="phone || email"
						class="-my-1 flex shrink-0 items-center"
						@click.stop
					>
						<FieldActionButtons
							:field="field"
							:value="doc[field.fieldname]"
							:record="actionRecord"
						/>
					</span>
				</div>
			</FieldBox>
			<ImagePreview
				v-if="imageUrl"
				v-model:open="previewing"
				:url="imageUrl"
				:title="field.label"
			/>
			<span
				v-if="message"
				:id="messageId"
				class="line-clamp-2 text-sm text-ink-red-6"
				:title="message"
			>
				{{ message }}
			</span>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref, useId, watch } from "vue";
import {
	CommitKey,
	ControlPageKey,
	DocKey,
	LinkTitlesKey,
	NO_COMMIT,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/FormLayout/types";
import { FieldErrorsKey, fieldErrorKey } from "@framework/ui/fields/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { RecordAnchor } from "@framework/ui/Link";
import {
	DataOpenLink,
	FieldActionButtons,
	FieldBox,
	FieldActionsKey,
	LinkMark,
	dataHref,
	fileName,
	focusField,
	isEmailField,
	isPhoneField,
	useLinkMark,
	useRecordLink,
} from "@framework/ui/fields";
import { isSummaryField, useFieldDisplay } from "@framework/ui/FormLayout";
import { __ } from "@/i18n";
import ImagePreview from "./ImagePreview.vue";
import { PanelContextKey, PanelFieldsKey } from "./context";

const props = defineProps<{ field: FieldNode }>();
const emit = defineEmits<{ expand: [field: FieldNode] }>();

const doc = inject(DocKey)!;
const update = inject(UpdateKey)!;
const commit = inject(CommitKey, NO_COMMIT);
const resolveField = inject(ResolveFieldKey)!;
const context = inject(PanelContextKey, null);
const page = inject(ControlPageKey, null);
// Only a script's own control gets `page`; the stock ones would carry it as a stray attribute.
// A stock control draws the panel's ghost box, so a `variant` in `ui.props` does not apply.
const controlProps = computed(() => {
	const { variant: _variant, ...stockProps } = props.field.ui?.props ?? {};
	if (!props.field.ui?.component)
		return {
			...stockProps,
			panel: true,
			errorId: messageId,
			...(phone.value || email.value ? { record: actionRecord.value } : {}),
		};
	return { ...props.field.ui.props, ...(page?.value ? { page: page.value } : {}) };
});
const titles = inject(LinkTitlesKey, null);
const displayField = useFieldDisplay();
const mark = useLinkMark(
	() => props.field,
	() => doc.value[props.field.fieldname]
);
const errors = inject(FieldErrorsKey, null);
const error = computed(() => errors?.value[fieldErrorKey(props.field.fieldname)]);
const message = computed(() => [error.value ?? []].flat().join(" "));
const messageId = useId();

function edit(fieldname: string, value: any) {
	update(fieldname, value);
	commit.pending(fieldname, value);
}

// A commit both closes the inline editor and fires the field's handler.
function onCommit(value: any) {
	editing.value = false;
	commit.commit(props.field.fieldname, value);
}

const editing = ref(false);
const cell = ref<HTMLElement | null>(null);
let opening: any;

// Every keystroke already wrote the draft, so a cancel has to put the opening value back.
function cancel() {
	if (!editing.value) return;
	update(props.field.fieldname, opening);
	editing.value = false;
}

// These act on one click in the box, with no editor to open or leave.
const IN_PLACE = ["Check", "Rating", "Color", "Attach", "Attach Image"];
const inPlace = computed(
	() => !props.field.ui?.component && IN_PLACE.includes(props.field.fieldtype)
);

// A field that Details does not draw has nowhere to open, so its row edits in place.
const summary = computed(
	() =>
		isSummaryField(props.field.fieldtype) &&
		!inPlace.value &&
		props.field.fieldtype !== "Image" &&
		(context?.onDetails(props.field.fieldname) ?? true)
);

// An Image row reads the Attach Image field its options name; it shows nothing when the panel
// already draws that field with its thumbnail.
const panelFields = inject(PanelFieldsKey, null);
const imageUrl = computed(() =>
	props.field.fieldtype === "Image" ? doc.value[props.field.options ?? ""] || "" : ""
);
const hidden = computed(
	() => props.field.fieldtype === "Image" && !!panelFields?.value.has(props.field.options ?? "")
);
const previewing = ref(false);
// Until every control takes `panel`, one that does not still draws its own error text.
const PANEL_FIELDTYPES = [
	"Data",
	"Int",
	"Float",
	"Currency",
	"Percent",
	"Phone",
	"Duration",
	"Password",
	...IN_PLACE,
];
const drawsErrorText = computed(
	() => !!props.field.ui?.component || !PANEL_FIELDTYPES.includes(props.field.fieldtype)
);
const interactive = computed(() => summary.value || !props.field.readOnly || !!imageUrl.value);
const resolved = computed(() => resolveField(props.field.fieldtype));

const placeholder = computed(() =>
	interactive.value && !summary.value && props.field.fieldtype !== "Image"
		? __("Add {0}...", [props.field.label])
		: ""
);

// The row draws the label; the control's one placeholder is the field's own, else `Add <Label>...`.
const controlField = computed(() => ({
	...props.field,
	label: undefined,
	description: undefined,
	placeholder: props.field.placeholder || placeholder.value,
}));

const display = computed(() =>
	displayField(props.field, doc.value[props.field.fieldname], { doc: doc.value })
);

// The row draws one dot per character, as the open input does, and never holds the value in the page.
const secret = computed(() =>
	props.field.fieldtype === "Password"
		? String(doc.value[props.field.fieldname] ?? "").length
		: 0
);
const phone = computed(() => isPhoneField(props.field));
const email = computed(() => isEmailField(props.field));
const actionRecord = computed(() =>
	context
		? { doctype: context.doctype, name: context.docname, surface: "record" as const }
		: undefined
);
const address = computed(() => dataHref(props.field, doc.value[props.field.fieldname]));
// The shell's email button already writes to this address, so the row drops its mailto arrow.
const fieldActions = inject(FieldActionsKey, null);
const composerEmail = computed(
	() =>
		email.value &&
		!!fieldActions
			?.for(props.field, doc.value[props.field.fieldname], actionRecord.value)
			.some((action) => action.act === "shell.email")
);

const record = useRecordLink(linkedDoctype, () => doc.value[props.field.fieldname] || null);
const openLabel = computed(() => {
	const title = titles?.value[`${linkedDoctype()}::${doc.value[props.field.fieldname]}`];
	return __("Open {0}", [title ?? display.value]);
});

function linkedDoctype(): string {
	const { fieldtype, options } = props.field;
	if (fieldtype === "Link") return options ?? "";
	if (fieldtype === "Dynamic Link" && options) return doc.value[options] ?? "";
	return "";
}

function open() {
	if (props.field.fieldtype === "Image") {
		previewing.value = !!imageUrl.value;
		return;
	}
	if (summary.value) return emit("expand", props.field);
	if (props.field.readOnly) return;
	opening = doc.value[props.field.fieldname];
	editing.value = true;
}

// A picker's popover is portalled out of the cell, so focus landing in it is not the user
// leaving the field.
const POPOVER =
	'[role="dialog"],[role="listbox"],[role="menu"],[data-reka-popper-content-wrapper]';

function onFocusout(event: FocusEvent) {
	const next = event.relatedTarget as HTMLElement | null;
	if (next && !isInside(next)) editing.value = false;
}

// A press on a blank part of the page moves focus nowhere, so `focusout` cannot tell it
// from a press in a popover.
function onPressOutside(event: PointerEvent) {
	const target = event.target as HTMLElement | null;
	if (target && !isInside(target)) editing.value = false;
}

function isInside(node: HTMLElement) {
	return !!cell.value?.contains(node) || !!node.closest(POPOVER);
}

watch(editing, async (on, _previous, onCleanup) => {
	if (!on) return;
	let stop = () => {};
	document.addEventListener("pointerdown", onPressOutside, true);
	onCleanup(() => {
		stop();
		document.removeEventListener("pointerdown", onPressOutside, true);
	});
	await nextTick();
	if (cell.value) stop = focusField(cell.value);
});
</script>
