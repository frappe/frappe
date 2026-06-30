<template>
	<Combobox
		:id="inputId"
		v-model="countryCode"
		v-model:open="countryPickerOpen"
		:options="countryOptions"
		:disabled="disabled"
		:size="size"
		:label="label"
		:description="description"
		:error="error"
		:required="required"
		:class="attrs.class"
		:style="attrs.style"
		placeholder="Search country"
		empty-text="No country found"
	>
		<template v-if="$slots.label" #label="slotProps">
			<slot name="label" v-bind="slotProps" />
		</template>
		<template v-if="$slots.description" #description>
			<slot name="description" />
		</template>
		<template #trigger="{ open }">
			<div
				data-slot="phone-input"
				v-bind="dataAttrs"
				:class="[inputClasses, hasLabeling ? null : (attrs.class as any)]"
				:style="hasLabeling ? null : (attrs.style as any)"
			>
				<!-- Selector: the only region allowed to toggle the popover. -->
				<button
					type="button"
					data-slot="country"
					:data-state="open ? 'open' : 'closed'"
					class="flex min-w-[50px] items-center justify-center gap-1 self-stretch rounded-l px-2 focus:outline-none"
					:class="disabled && 'cursor-not-allowed'"
					:disabled="disabled"
					:aria-label="
						phoneDetails.country
							? `Country: ${phoneDetails.country.name}`
							: 'Select country'
					"
					aria-haspopup="listbox"
					:aria-expanded="open"
				>
					<img
						v-if="phoneDetails.country"
						:src="getFlagUrl(phoneDetails.country)"
						:alt="phoneDetails.country.name"
						class="h-3 w-4 rounded-sm object-cover"
					/>
					<!-- Same-size placeholder so the chevron never shifts. -->
					<span v-else class="lucide-globe size-4 shrink-0 text-ink-gray-6" />
					<span
						class="lucide-chevron-down size-4 shrink-0 text-ink-gray-6 transition-transform duration-200 ease-[cubic-bezier(0.23,1,0.32,1)]"
						:class="open && 'rotate-180'"
					/>
				</button>

				<!--
            Presses right of the selector must never toggle the popover, so
            this region stops click/pointerdown (spec/combobox.md rule for
            interactive elements inside #trigger content).
          -->
				<div
					class="flex min-w-0 flex-1 items-center self-stretch"
					@click.stop
					@pointerdown.stop="countryPickerOpen = false"
				>
					<!-- Divider: one step darker on hover so it doesn't blend into
                 the shell's hover background (surface-gray-3 ≈ outline-gray-2). -->
					<div class="self-stretch border-l border-outline-gray-2" aria-hidden="true" />
					<!-- ISD Code -->
					<span v-if="phoneDetails.country" class="select-none ps-2" :class="textColor">
						{{ phoneDetails.country.isd }}
					</span>
					<!-- Number Input -->
					<input
						:id="inputId"
						ref="numberInputRef"
						v-model="phoneDetails.number"
						data-slot="control"
						type="tel"
						inputmode="tel"
						autocomplete="tel"
						:class="numberInputClasses"
						:placeholder="placeholder"
						:disabled="disabled"
						:required="required"
						:aria-required="required || undefined"
						:aria-invalid="hasError || undefined"
						:aria-errormessage="hasError ? errorMessageId : undefined"
						:aria-describedby="describedBy"
						v-bind="attrsWithoutClassStyle"
						@keydown.backspace="onBackspace"
					/>
					<div v-if="$slots.suffix" class="flex items-center gap-2 pe-2.5">
						<slot name="suffix" />
					</div>
				</div>
			</div>
		</template>

		<template #item="{ item, selected }">
			<div class="w-[calc(var(--reka-combobox-trigger-width)-0.5rem)]">
				<ItemListRow :size="size" :selected="selected">
					<template #prefix>
						<!-- Decorative: the country name is the adjacent text. -->
						<img
							:src="getFlagUrl(item.country)"
							alt=""
							class="h-3 w-4 rounded-sm object-cover"
							loading="lazy"
							decoding="async"
						/>
					</template>
					<template #label>
						<div class="truncate">{{ item.country.name }}</div>
					</template>
					<template #suffix>
						<span class="text-ink-gray-5">{{ item.country.isd }}</span>
					</template>
				</ItemListRow>
			</div>
		</template>
	</Combobox>
</template>

<script setup lang="ts">
import { Combobox, ItemListRow } from "frappe-ui";
import { inputFontSizeClasses, useInputLabeling } from "frappe-ui/experimental";
import { computed, nextTick, onMounted, reactive, ref, useAttrs, useSlots, watch } from "vue";
import type { Country, PhoneInputProps, PhoneInputSlots } from "./types";
import {
	countries,
	getCountryFromCode,
	getFlagUrl,
	guessCountryFromTimezone,
	joinPhoneDetails,
	splitPhoneDetails,
} from "./utils";

defineOptions({
	inheritAttrs: false,
});

const props = withDefaults(defineProps<PhoneInputProps>(), {
	size: "sm",
	variant: "subtle",
});

const model = defineModel<string>({ default: "" });

defineSlots<PhoneInputSlots>();

const attrs = useAttrs();
const slots = useSlots();

const attrsWithoutClassStyle = computed(() => {
	return Object.fromEntries(
		Object.entries(attrs).filter(([key]) => key !== "class" && key !== "style")
	);
});

const { inputId, errorMessageId, describedBy, hasError, dataAttrs } = useInputLabeling(props, {
	size: () => props.size,
	variant: () => props.variant,
	disabled: () => props.disabled,
});

const hasLabeling = computed(() => {
	return Boolean(
		props.label || props.description || hasError.value || slots.label || slots.description
	);
});

const phoneDetails = reactive<{ country: Country | null; number: string }>({
	country: null,
	number: "",
});

const numberInputRef = ref<HTMLInputElement | null>(null);

// Controlled because the whole shell is the popover anchor: presses on the
// number-input region count as "inside" for reka's outside-press dismiss,
// so the region closes the picker itself (see the template's pointerdown).
const countryPickerOpen = ref(false);

// The ISD lives inside `label` so Combobox's built-in filtering matches
// country name and dial code alike; the slots render name and ISD apart.
const countryOptions = countries.map((country) => ({
	label: `${country.name} ${country.isd}`,
	value: country.code,
	country,
}));

const countryCode = computed<string | null>({
	get: () => phoneDetails.country?.code ?? null,
	set: (code) => {
		const country = getCountryFromCode(code);
		if (!country) return;
		phoneDetails.country = country;
		nextTick(() => numberInputRef.value?.focus());
	},
});

const textColor = computed(() => {
	return props.disabled ? "text-ink-gray-5" : "text-ink-gray-8";
});

const numberInputClasses = computed(() => [
	"h-full min-w-0 flex-1 border-0 bg-transparent ps-1 pe-2 outline-none focus:ring-0 focus-visible:ring-0 disabled:cursor-not-allowed",
	textColor.value,
	inputFontSizeClasses(props.size),
	props.disabled ? "placeholder-ink-gray-3" : "placeholder-ink-gray-4",
]);

const inputClasses = computed(() => {
	const sizeClasses = {
		sm: "h-7 rounded",
		md: "h-8 rounded",
		lg: "h-10 rounded-md",
		xl: "h-10 rounded-md",
	}[props.size];

	const variantClasses = props.disabled
		? [
				"cursor-not-allowed border bg-surface-gray-1",
				props.variant === "outline" ? "border-outline-gray-2" : "border-transparent",
		  ]
		: {
				subtle: "border border-[--surface-gray-2] bg-surface-gray-2 hover:border-outline-elevation-2 hover:bg-surface-gray-3 focus-within:bg-surface-base focus-within:border-outline-gray-4 focus-within:shadow-sm focus-within:hover:bg-surface-base focus-within:hover:border-outline-gray-4",
				outline:
					"border border-outline-gray-2 bg-surface-base hover:border-outline-gray-3 hover:shadow-sm focus-within:bg-surface-base focus-within:border-outline-gray-4 focus-within:shadow-sm focus-within:hover:border-outline-gray-4",
		  }[props.variant];

	return [
		// Keyboard focus ring, mirroring TextInput's `focus-visible:ring-2`
		// one level up: the inner input is chromeless, so the shell rings
		// when any child has keyboard focus.
		"flex w-full items-center transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-outline-gray-3",
		sizeClasses,
		inputFontSizeClasses(props.size),
		variantClasses,
	];
});

function onBackspace() {
	if (!phoneDetails.number) phoneDetails.country = null;
}

// Splits a raw value into country + number state.
function setPhoneValue(value: string) {
	const parsed = splitPhoneDetails(value);
	phoneDetails.number = parsed.number;
	if (parsed.country && parsed.country.isd !== phoneDetails.country?.isd) {
		phoneDetails.country = parsed.country;
	}
}

// Values typed, pasted, or autofilled into the input carrying an ISD
// ("+9198…") re-route through the parser before the model emits.
watch(
	() => phoneDetails.number,
	(value) => {
		if (value.startsWith("+")) setPhoneValue(value);
	}
);

watch(phoneDetails, () => {
	model.value = joinPhoneDetails(phoneDetails.country, phoneDetails.number);
});

// parses input to +country+number and updates the model.
watch(model, (value) => {
	if (value === joinPhoneDetails(phoneDetails.country, phoneDetails.number)) return;
	setPhoneValue(value ?? "");
});

onMounted(() => {
	const parsed = splitPhoneDetails(model.value);
	phoneDetails.country = parsed.country ?? (model.value ? null : guessCountryFromTimezone());
	phoneDetails.number = parsed.number;
});

defineExpose({ el: numberInputRef });
</script>

<style scoped>
/*
 * Same rule ComboboxResults applies to its default rows: the outer item
 * paints highlight / selected backgrounds (including the combined state),
 * so ItemListRow's own bg must stay transparent for it to show through.
 */
[data-slot="item"] [data-slot="item-list-row"] {
	background-color: transparent;
}

/*
 * Browsers force-paint autofilled inputs
 */
input:-webkit-autofill {
	-webkit-background-clip: text;
	background-clip: text;
}

input:autofill {
	-webkit-background-clip: text;
	background-clip: text;
}
</style>
