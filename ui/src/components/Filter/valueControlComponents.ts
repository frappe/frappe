import { defineAsyncComponent, type Component } from "vue";
import { Select, TextInput } from "frappe-ui";
// The shared, fieldtype-aware value inputs. Only the subset that needs no form
// context is mounted here, so an input that would resolve currency from a form
// falls back to site defaults.
import SelectField from "../Fields/SelectField.vue";
import LinkField from "../Fields/LinkField.vue";
import NumberField from "../Fields/NumberField.vue";
import DateField from "../Fields/DateField.vue";
import DatetimeField from "../Fields/DatetimeField.vue";
import DurationField from "../Fields/DurationField.vue";
import type { ValueControlId } from "./valueControl";

type LazyControl = keyof typeof import("./lazyControls");

/** Loads one popover-only input from the lazy module; later calls reuse the chunk. */
function lazyControl(name: LazyControl): Component {
  return defineAsyncComponent(() =>
    import("./lazyControls").then((module) => module[name] as Component)
  );
}

/** Fetches the lazy module, so a popover opens with its inputs drawn. */
export function preloadControls(): void {
  // A failed fetch retries when an input first renders; staleBuild asks for a reload.
  import("./lazyControls").catch(() => {});
}

/**
 * The component behind each {@link ValueControlId}. Kept apart from
 * `valueControl.ts` so the dispatch rules stay free of `.vue` imports.
 */
export const VALUE_CONTROLS: Record<ValueControlId, Component> = {
  set: Select,
  timespan: Select,
  multiSelect: lazyControl("MultiSelectInput"),
  multiLink: lazyControl("MultiLinkInput"),
  text: TextInput,
  select: SelectField,
  link: LinkField,
  number: NumberField,
  dateRange: lazyControl("DateRangePicker"),
  date: DateField,
  datetime: DatetimeField,
  duration: DurationField,
  rating: lazyControl("RatingField"),
};
