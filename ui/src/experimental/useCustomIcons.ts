import { computed } from "vue";
import type { ComputedRef } from "vue";
import { createResource } from "frappe-ui";
import type { IconPickerSection } from "./IconPicker/IconPicker.vue";

export const CUSTOM_ICON_PREFIX = "custom:";

export function isCustomIconName(name: string | null | undefined): boolean {
  return !!name && name.startsWith(CUSTOM_ICON_PREFIX);
}

interface CustomIconRow {
  name: string;
  svg: string;
}

export interface UseCustomIcons {
  names: ComputedRef<string[]>;
  sections: ComputedRef<IconPickerSection[]>;
  svgFor: (name: string) => string | null;
  reload: () => void;
}

const resource = createResource({
  url: "frappe.client.get_list",
  params: {
    doctype: "Custom Icon",
    fields: ["name", "svg"],
    limit_page_length: 0,
  },
  cache: "customIcons",
  auto: true,
  onError: () => {},
});

function rows(): CustomIconRow[] {
  return (resource.data as CustomIconRow[] | null) ?? [];
}

const svgBySlug = computed(
  () => new Map(rows().map((row) => [row.name, row.svg] as [string, string]))
);

function svgFor(name: string): string | null {
  return svgBySlug.value.get(name.slice(CUSTOM_ICON_PREFIX.length)) ?? null;
}

const names = computed(() =>
  rows().map((row) => CUSTOM_ICON_PREFIX + row.name)
);

const sections = computed<IconPickerSection[]>(() =>
  names.value.length
    ? [
        {
          label: "Custom",
          options: names.value.map((value) => ({
            value,
            label: value.slice(CUSTOM_ICON_PREFIX.length),
            svg: svgFor(value) ?? undefined,
          })),
        },
      ]
    : []
);

export function useCustomIcons(): UseCustomIcons {
  return {
    names,
    sections,
    svgFor,
    reload: () => resource.reload(),
  };
}
