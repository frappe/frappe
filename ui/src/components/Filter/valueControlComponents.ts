import type { Component } from "vue";
import { Select, TextInput, DateRangePicker } from "frappe-ui";
// A static list for Select/Autocomplete, a live link search for Link.
import MultiSelectInput from "./MultiSelectInput.vue";
import MultiLinkInput from "./MultiLinkInput.vue";
// The shared, fieldtype-aware value inputs. Only the subset that needs no form
// context is mounted here, so an input that would resolve currency from a form
// falls back to site defaults.
import SelectField from "../Fields/SelectField.vue";
import LinkField from "../Fields/LinkField.vue";
import NumberField from "../Fields/NumberField.vue";
import DateField from "../Fields/DateField.vue";
import DatetimeField from "../Fields/DatetimeField.vue";
import DurationField from "../Fields/DurationField.vue";
import RatingField from "../Fields/RatingField.vue";
import type { ValueControlId } from "./valueControl";

/**
 * The component behind each {@link ValueControlId}. Kept apart from
 * `valueControl.ts` so the dispatch rules stay free of `.vue` imports.
 */
export const VALUE_CONTROLS: Record<ValueControlId, Component> = {
  set: Select,
  timespan: Select,
  multiSelect: MultiSelectInput,
  multiLink: MultiLinkInput,
  text: TextInput,
  select: SelectField,
  link: LinkField,
  number: NumberField,
  dateRange: DateRangePicker,
  date: DateField,
  datetime: DatetimeField,
  duration: DurationField,
  rating: RatingField,
};
