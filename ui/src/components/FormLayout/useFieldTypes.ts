import type { Component } from "vue";
import { getFieldComponent, registerFieldType } from "../Fields/fieldTypes";

/** Composable over the fieldtype registry: register custom types, resolve one. */
export function useFieldTypes() {
  return {
    register: (fieldtype: string, component: Component) =>
      registerFieldType(fieldtype, component),
    resolve: (fieldtype: string): Component => getFieldComponent(fieldtype),
  };
}
