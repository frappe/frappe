import { describe, expect, it } from "vitest";
import { defineComponent } from "vue";
import { getFieldComponent, registerFieldType } from "../fieldTypes";
import AutocompleteField from "../fields/AutocompleteField.vue";
import CheckField from "../fields/CheckField.vue";
import DateField from "../fields/DateField.vue";
import DatetimeField from "../fields/DatetimeField.vue";
import DurationField from "../fields/DurationField.vue";
import DynamicLinkField from "../fields/DynamicLinkField.vue";
import HeadingField from "../fields/HeadingField.vue";
import HtmlField from "../fields/HtmlField.vue";
import LinkField from "../fields/LinkField.vue";
import NumberField from "../fields/NumberField.vue";
import PasswordField from "../fields/PasswordField.vue";
import PhoneField from "../fields/PhoneField.vue";
import RatingField from "../fields/RatingField.vue";
import SelectField from "../fields/SelectField.vue";
import TableMultiSelectField from "../fields/TableMultiSelectField.vue";
import TextField from "../fields/TextField.vue";
import TextareaField from "../fields/TextareaField.vue";
import TimeField from "../fields/TimeField.vue";

describe("fieldTypes registry", () => {
  it("resolves a registered fieldtype", () => {
    expect(getFieldComponent("Link")).toBe(LinkField);
  });

  it("resolves each new single-key fieldtype to its component", () => {
    expect(getFieldComponent("Select")).toBe(SelectField);
    expect(getFieldComponent("Check")).toBe(CheckField);
    expect(getFieldComponent("Date")).toBe(DateField);
    expect(getFieldComponent("Datetime")).toBe(DatetimeField);
    expect(getFieldComponent("Time")).toBe(TimeField);
    expect(getFieldComponent("Password")).toBe(PasswordField);
  });

  it("resolves all number fieldtypes to NumberField", () => {
    for (const t of ["Int", "Float", "Currency", "Percent"]) {
      expect(getFieldComponent(t)).toBe(NumberField);
    }
  });

  it("resolves all multi-line text fieldtypes to TextareaField", () => {
    // Includes the code-family types that ride on the textarea until a real
    // CodeEditorField exists (JSON / Markdown Editor / HTML Editor / Code).
    for (const t of [
      "Small Text",
      "Text",
      "Long Text",
      "Code",
      "JSON",
      "Markdown Editor",
      "HTML Editor",
    ]) {
      expect(getFieldComponent(t)).toBe(TextareaField);
    }
  });

  it("resolves Phone, Heading, and HTML to their components", () => {
    expect(getFieldComponent("Phone")).toBe(PhoneField);
    expect(getFieldComponent("Heading")).toBe(HeadingField);
    expect(getFieldComponent("HTML")).toBe(HtmlField);
  });

  it("resolves the picker/selector fieldtypes to their components", () => {
    expect(getFieldComponent("Autocomplete")).toBe(AutocompleteField);
    expect(getFieldComponent("Rating")).toBe(RatingField);
    expect(getFieldComponent("Duration")).toBe(DurationField);
    expect(getFieldComponent("Dynamic Link")).toBe(DynamicLinkField);
    expect(getFieldComponent("Table MultiSelect")).toBe(TableMultiSelectField);
  });

  it("falls back to the text component for an unknown fieldtype", () => {
    expect(getFieldComponent("NotARealFieldtype")).toBe(TextField);
  });

  it("register overrides what resolve returns", () => {
    const custom = defineComponent({ name: "Custom", render: () => null });
    registerFieldType("Link", custom);
    expect(getFieldComponent("Link")).toBe(custom);

    // restore so the override does not leak into other tests
    registerFieldType("Link", LinkField);
    expect(getFieldComponent("Link")).toBe(LinkField);
  });
});
