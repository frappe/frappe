import { describe, expect, it } from "vitest";
import { defineComponent } from "vue";
import { getFieldComponent, registerFieldType } from "../fieldTypes";
import AutocompleteField from "../AutocompleteField.vue";
import ButtonField from "../ButtonField.vue";
import CheckField from "../CheckField.vue";
import CodeEditorField from "../CodeEditorField.vue";
import DateField from "../DateField.vue";
import DatetimeField from "../DatetimeField.vue";
import DurationField from "../DurationField.vue";
import DynamicLinkField from "../DynamicLinkField.vue";
import AttachField from "../AttachField.vue";
import ImageField from "../ImageField.vue";
import GeolocationField from "../GeolocationField.vue";
import HeadingField from "../HeadingField.vue";
import HtmlField from "../HtmlField.vue";
import LinkField from "../LinkField.vue";
import NumberField from "../NumberField.vue";
import PasswordField from "../PasswordField.vue";
import PhoneField from "../PhoneField.vue";
import RatingField from "../RatingField.vue";
import SelectField from "../SelectField.vue";
import TableMultiSelectField from "../TableMultiSelectField.vue";
import TextField from "../TextField.vue";
import TextareaField from "../TextareaField.vue";
import TimeField from "../TimeField.vue";

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
    for (const t of ["Small Text", "Text", "Long Text"]) {
      expect(getFieldComponent(t)).toBe(TextareaField);
    }
  });

  it("resolves the code-family fieldtypes to CodeEditorField", () => {
    // JSON / Markdown Editor / HTML Editor / Code share one CodeMirror-backed
    // field (moved off TextareaField).
    for (const t of ["Code", "JSON", "Markdown Editor", "HTML Editor"]) {
      expect(getFieldComponent(t)).toBe(CodeEditorField);
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

  it("resolves Geolocation to its component", () => {
    expect(getFieldComponent("Geolocation")).toBe(GeolocationField);
  });

  it("resolves Attach and Attach Image to the shared AttachField", () => {
    expect(getFieldComponent("Attach")).toBe(AttachField);
    expect(getFieldComponent("Attach Image")).toBe(AttachField);
  });

  it("resolves Image to the display-only ImageField", () => {
    expect(getFieldComponent("Image")).toBe(ImageField);
  });

  it("resolves Button to its component", () => {
    expect(getFieldComponent("Button")).toBe(ButtonField);
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
