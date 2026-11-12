<!-- One panel row: the label in a fixed column, the value in the flexible one. -->
<template>
	<div v-if="!hidden" class="grid grid-cols-[130px_1fr] items-start gap-2">
		<PanelLabel :field="field" :tip="tip" />
		<FieldDescription
			v-if="field.description"
			:id="descriptionId"
			:html="field.description"
			class="sr-only"
		/>

		<div
			ref="wrapper"
			class="min-w-0"
			@pointerdown.capture="press"
			@focusin="onRowFocusin"
			@focusout="onRowFocusout"
		>
			<component
				:is="bare ? 'div' : FieldBox"
				class="group"
				v-bind="bare ? {} : { interactive, error: !!message }"
			>
				<div
					v-if="editing || inPlace"
					ref="cell"
					class="field min-w-0"
					:style="restHeight ? { '--panel-rest-h': `${restHeight}px` } : undefined"
					:data-fieldname="field.fieldname"
					@focusin="describe"
					@focusout="onFocusout"
					@keydown.capture="onCellKey"
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
					class="flex min-h-7 min-w-0 flex-wrap items-center gap-x-1.5"
					:class="[
						interactive && pickable ? 'cursor-pointer' : '',
						chips && interactive && pickable ? 'ps-2 pe-[30px]' : 'px-2',
					]"
					:data-fieldname="field.fieldname"
					ref="rest"
					:role="imageUrl ? 'button' : undefined"
					:tabindex="focusable ? 0 : undefined"
					:aria-describedby="field.description ? descriptionId : undefined"
					@click="open"
					@focus="onRestFocus"
					@keydown.self="onRestKey"
				>
					<span v-if="chips" class="flex min-w-0 flex-1 flex-wrap gap-1 py-1">
						<SelectedChip
							v-for="(chip, index) in chipList"
							:key="index"
							:label="chip"
							:removable="interactive ? false : undefined"
							panel
						/>
						<span
							v-if="!chipList.length && pickable"
							class="text-base leading-5 text-ink-gray-4"
							>{{ placeholder }}</span
						>
						<span
							v-if="!pickable"
							class="leading-5 text-ink-gray-5"
							:class="chipList.length ? 'basis-full text-sm' : 'text-base'"
							>{{ __("Child table metadata unavailable") }}</span
						>
					</span>
					<span v-else-if="multiline" class="min-w-0 flex-1 py-1">
						<span
							ref="clamped"
							class="line-clamp-6 text-base leading-5 break-words whitespace-pre-wrap"
							:class="valueColor"
							>{{ display || placeholder }}</span
						>
					</span>
					<span
						v-else
						class="flex min-w-0 flex-1 items-center text-base leading-7"
						:class="valueColor"
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
			</component>
			<ImagePreview
				v-if="imageUrl"
				v-model:open="previewing"
				:url="imageUrl"
				:title="field.label"
			/>
			<span
				v-if="message"
				:id="messageId"
				class="line-clamp-2 px-2 text-sm text-ink-red-6"
				:title="message"
			>
				{{ message }}
			</span>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
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
	FieldDescription,
	FieldActionsKey,
	SelectedChip,
	LinkMark,
	dataHref,
	fileName,
	focusField,
	isEmailField,
	isPhoneField,
	useLinkMark,
	useRecordLink,
} from "@framework/ui/fields";
import { isSummaryField, selectedLinks, useFieldDisplay } from "@framework/ui/FormLayout";
import { __ } from "@/i18n";
import { htmlToText, isEmptyHtml } from "@framework/ui/RichText";
import ImagePreview from "./ImagePreview.vue";
import { PanelContextKey, PanelFieldsKey } from "./context";
import { withoutOwnRecordPrefix } from "./ownRecordPrefix";
import { placeCaret, placeCaretAtPoint, textOffsetAt } from "./openAtClick";
import PanelLabel from "./PanelLabel.vue";

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
			panel: !inPlaceHeavy.value,
			...(drawsErrorText.value ? {} : { errorId: messageId }),
			openPicker: pointerOpen.value,
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
const message = computed(() => {
	const { doctype, name } = doc.value;
	return [error.value ?? []]
		.flat()
		.map((one) => withoutOwnRecordPrefix(one, [doctype, __(doctype)], name))
		.join(" ");
});
const messageId = useId();
const descriptionId = useId();

function edit(fieldname: string, value: any) {
	if (cancelled) return;
	update(fieldname, value);
	commit.pending(fieldname, value);
}

// A commit both closes the inline editor and fires the field's handler.
function onCommit(value: any) {
	if (cancelled) return;
	editing.value = false;
	commit.commit(props.field.fieldname, value);
}

const editing = ref(false);
const pointerOpen = ref(false);
const cell = ref<HTMLElement | null>(null);
const clamped = ref<HTMLElement | null>(null);
let opening: any;
// Removing the focused input fires `change`, which would write the cancelled draft back.
let cancelled = false;
// Where in the text a click opened a multi-line row, so the caret lands under the pointer.
let clicked: number | null = null;
// The same for a rich-text row, whose body is not a textarea: the point of the click.
let clickedAt: { x: number; y: number } | null = null;
// The row's height at rest: an editor that loads lazily holds this much space until it draws.
const restHeight = ref(0);

// Every keystroke already wrote the draft, so a cancel has to put the opening value back.
function cancel() {
	if (!editing.value) return;
	keepFocus = true;
	cancelled = true;
	commit.discard(props.field.fieldname);
	update(props.field.fieldname, opening);
	editing.value = false;
}

// These act on one click in the box, with no editor to open or leave.
const IN_PLACE = ["Check", "Rating", "Color", "Attach", "Attach Image", "Geolocation"];
const inPlace = computed(
	() => !props.field.ui?.component && IN_PLACE.includes(props.field.fieldtype)
);

// These keep the summary read views, yet edit in their row like Long Text.
const TEXT_EDITORS = ["Text Editor", "Markdown Editor"];
const textEditor = computed(() => TEXT_EDITORS.includes(props.field.fieldtype));

// A field that Details does not draw has nowhere to open, so its row edits in place.
const summary = computed(
	() =>
		isSummaryField(props.field.fieldtype) &&
		!inPlace.value &&
		!textEditor.value &&
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
const MULTILINE = ["Small Text", "Text", "Long Text", ...TEXT_EDITORS];
const PANEL_FIELDTYPES = [
	"Data",
	"Small Text",
	"Text",
	"Long Text",
	"Table MultiSelect",
	"Int",
	"Float",
	"Currency",
	"Percent",
	"Phone",
	"Duration",
	"Password",
	...TEXT_EDITORS,
	...IN_PLACE,
	"Link",
	"Dynamic Link",
	"Select",
	"Autocomplete",
	"Date",
	"Datetime",
	"Time",
];
const drawsErrorText = computed(
	() => !!props.field.ui?.component || !PANEL_FIELDTYPES.includes(props.field.fieldtype)
);
// A bare row is only a script's own: a stock control draws a ghost input that needs the box.
const bare = computed(() => !!props.field.ui?.component && !!props.field.ui.ownBox);
// A heavy field that Details does not draw edits in place with no `panel` look.
const inPlaceHeavy = computed(
	() =>
		isSummaryField(props.field.fieldtype) &&
		!summary.value &&
		!inPlace.value &&
		!textEditor.value
);
const multiline = computed(() => MULTILINE.includes(props.field.fieldtype));
const chips = computed(() => props.field.fieldtype === "Table MultiSelect");
// Without the child table's Link field there is nothing to pick from, so the row stays closed.
const pickable = computed(
	() => !chips.value || !!props.field.childFields?.find((f) => f.fieldtype === "Link")?.options
);
const chipList = computed(() =>
	selectedLinks(doc.value[props.field.fieldname], props.field, titles?.value ?? {})
);
const valueColor = computed(() =>
	error.value ? "text-ink-red-6" : display.value ? "text-ink-gray-8" : "text-ink-gray-4"
);
const interactive = computed(() => summary.value || !props.field.readOnly || !!imageUrl.value);
const resolved = computed(() => resolveField(props.field.fieldtype));

// The field's own placeholder shows at rest, on hover and in the editor; `Add <Label>...` only without one.
// A Geolocation row reads "Set location" when empty, as in Details.
const placeholder = computed(() =>
	interactive.value &&
	!summary.value &&
	props.field.fieldtype !== "Image" &&
	props.field.fieldtype !== "Geolocation"
		? props.field.placeholder || __("Add {0}...", [props.field.label])
		: ""
);

const controlField = computed(() => ({
	...props.field,
	label: undefined,
	description: undefined,
	placeholder: placeholder.value,
}));

// A Text Editor row shows the text of its HTML and a Markdown Editor row its source, over the
// lines the open editor shows; the summary read views show one line.
const display = computed(() => {
	const value = doc.value[props.field.fieldname];
	if (props.field.fieldtype === "Text Editor") return richTextLine(value);
	if (props.field.fieldtype === "Markdown Editor") return String(value ?? "");
	return displayField(props.field, value, { doc: doc.value });
});

// A value of only an image has no text, yet is not empty.
function richTextLine(html: string | null | undefined) {
	const text = htmlToText(html);
	if (text || isEmptyHtml(html)) return text;
	return /<img\b/i.test(html ?? "") ? __("Image") : __("Media");
}

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

// A pointer open also opens a picker's popover; any other open leaves it closed.
function open(event?: Event, picker = event instanceof MouseEvent) {
	if (props.field.fieldtype === "Image") {
		previewing.value = !!imageUrl.value;
		return;
	}
	if (summary.value) return emit("expand", props.field);
	if (props.field.readOnly || !pickable.value) return;
	opening = doc.value[props.field.fieldname];
	cancelled = false;
	clicked = null;
	restHeight.value = clamped.value?.closest<HTMLElement>("[data-fieldname]")?.offsetHeight ?? 0;
	clickedAt =
		event instanceof MouseEvent && props.field.fieldtype === "Text Editor"
			? { x: event.clientX, y: event.clientY }
			: null;
	// The shown text is the value only when no formatting stands between them; a textarea turns
	// `\r\n` into `\n`, which would shift every offset after it.
	const shown = String(opening ?? "");
	if (
		event instanceof MouseEvent &&
		clamped.value &&
		shown === display.value &&
		!shown.includes("\r")
	)
		clicked = textOffsetAt(clamped.value, event.clientX, event.clientY);
	pointerOpen.value = picker;
	editing.value = true;
}

// Each editable row is one tab stop: a focus that is not a press opens its editor with no popover.
// Enter and Alt+↓ open it, and so does typing, which keeps the key that opened it.
const rest = ref<HTMLElement | null>(null);
const wrapper = ref<HTMLElement | null>(null);
const tip = ref(false);
const focusable = computed(() => interactive.value && pickable.value);
// A press focuses the row before its click opens the editor; the focus must not open it too.
let pressed = false;
// Enter or Esc closed the editor: the closed row keeps focus and stays shut.
let keepFocus = false;
let restoring = false;
// Keys typed before the editor has focus, typed into it once it has.
let typed = "";

function onRestFocus() {
	if (pressed || restoring || summary.value || imageUrl.value) return;
	open();
}
function onRestKey(event: KeyboardEvent) {
	const opensOnly = summary.value || !!imageUrl.value;
	if (event.altKey && event.key === "ArrowDown") {
		event.preventDefault();
		return open(undefined, true);
	}
	if (event.key === "Enter" || (opensOnly && event.key === " ")) {
		event.preventDefault();
		return open();
	}
	if (opensOnly || !focusable.value || !isTyping(event)) return;
	event.preventDefault();
	typed += event.key;
	open();
}
function isTyping(event: KeyboardEvent) {
	return event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey;
}
function onCellKey(event: KeyboardEvent) {
	keepFocus = event.key === "Enter" && !(event.target instanceof HTMLTextAreaElement);
}
// Q21: a screen reader reads the label's description with the field that takes focus.
function describe(event: FocusEvent) {
	const target = event.target as HTMLElement;
	if (!props.field.description || cell.value?.contains(event.relatedTarget as Node)) return;
	const ids = new Set(target.getAttribute("aria-describedby")?.split(" "));
	target.setAttribute("aria-describedby", [...ids, descriptionId].join(" ").trim());
}
// The label's tip shows while a key, not a press, holds focus in the row.
function onRowFocusin() {
	if (!pressed) tip.value = true;
}
function onRowFocusout() {
	setTimeout(() => {
		if (!wrapper.value?.contains(document.activeElement)) tip.value = false;
	});
}
function press() {
	pressed = true;
}
function releasePress() {
	setTimeout(() => (pressed = false));
}
onMounted(() => document.addEventListener("pointerup", releasePress, true));
onBeforeUnmount(() => document.removeEventListener("pointerup", releasePress, true));
async function keepFocusOnRow() {
	keepFocus = false;
	await nextTick();
	restoring = true;
	rest.value?.focus();
	restoring = false;
}

// A picker's popover is portalled out of the cell, so focus landing in it is not the user
// leaving the field.
const POPOVER =
	'[role="dialog"],[role="listbox"],[role="menu"],[data-reka-popper-content-wrapper],[data-slot="table-menu"]';

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

// reka's Select keeps Tab inside its portalled list; moving focus to the row's control first lets the Tab walk on.
function leaveList(event: KeyboardEvent) {
	if (event.key !== "Tab" || !(event.target as HTMLElement).closest(POPOVER)) return;
	const control = cell.value?.querySelector<HTMLElement>("input, textarea, select, button");
	if (!control) return;
	event.stopPropagation();
	control.focus();
}
function holdTyping(event: KeyboardEvent) {
	if (!isTyping(event) || cell.value?.contains(document.activeElement)) return;
	event.preventDefault();
	typed += event.key;
}
function typeHeld() {
	if (typed) document.execCommand("insertText", false, typed);
	typed = "";
}
watch(editing, async (on, _previous, onCleanup) => {
	if (!on) return keepFocus ? keepFocusOnRow() : undefined;
	let stop = () => {};
	document.addEventListener("pointerdown", onPressOutside, true);
	document.addEventListener("keydown", holdTyping, true);
	document.addEventListener("keydown", leaveList, true);
	onCleanup(() => {
		document.removeEventListener("keydown", leaveList, true);
		stop();
		document.removeEventListener("pointerdown", onPressOutside, true);
		document.removeEventListener("keydown", holdTyping, true);
	});
	await nextTick();
	if (!cell.value) return;
	// The body loads on first use, so the caret waits for the focus it takes.
	const at = clickedAt;
	if (at) {
		const host = cell.value;
		host.addEventListener("focusin", () => placeCaretAtPoint(host, at.x, at.y), {
			once: true,
		});
	}
	stop = focusField(cell.value);
	const area = multiline.value && cell.value.querySelector("textarea");
	if (area) placeCaret(area, clicked);
	if (cell.value.contains(document.activeElement)) return typeHeld();
	cell.value.addEventListener("focusin", typeHeld, { once: true });
});
</script>
