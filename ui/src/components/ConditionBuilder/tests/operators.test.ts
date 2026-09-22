import { describe, expect, it } from "vitest";
import { carryOver } from "../../Filter/operators";
import type { Filter } from "../../Filter/types";
import type { ConditionField } from "../types";
import { conditionOperators } from "../adapters";

const status: ConditionField = {
  label: "Status",
  value: "status",
  fieldname: "status",
  fieldtype: "Select",
  options: "Open\nReplied",
};

const priority: ConditionField = {
  label: "Priority",
  value: "priority",
  fieldname: "priority",
  fieldtype: "Select",
  options: "Low\nHigh",
};

describe("carryOver", () => {
  it("keeps an operator the caller offers but Filter does not", () => {
    // `is not` exists only in `conditionOperators`. Checked against
    // `getOperators` it reads as unavailable on every field, so changing the
    // field silently reset the row and lost both operator and value.
    const prev: Filter = {
      field: status,
      fieldname: "status",
      operator: "is not",
      value: "set",
    };

    const carried = carryOver(
      prev,
      priority,
      conditionOperators(priority.fieldtype, priority.fieldname)
    );

    expect(carried.operator).toBe("is not");
    expect(carried.value).toBe("set");
    expect(carried.fieldname).toBe("priority");
  });

  it("still resets an operator the new field is not offered", () => {
    const prev: Filter = {
      field: status,
      fieldname: "status",
      operator: "between",
      value: ["a", "b"],
    };

    const carried = carryOver(
      prev,
      priority,
      conditionOperators(priority.fieldtype, priority.fieldname)
    );

    expect(carried.operator).not.toBe("between");
  });

  it("drops a deleted field's value where the new field cannot hold it", () => {
    // A row whose own field was removed from the doctype: `prev.field` is
    // undefined, so there is no domain to compare and the value is whatever
    // text the record stored. Carried into a Date it made `creation == "Open"`
    // offered, because `equals` is a Date operator, and handed the value
    // straight to a DateField.
    const gone: Filter = {
      field: undefined,
      fieldname: "deleted_field",
      operator: "equals",
      value: "Open",
    };

    const created: ConditionField = {
      label: "Created On",
      value: "creation",
      fieldname: "creation",
      fieldtype: "Datetime",
    };

    const subject: ConditionField = {
      label: "Subject",
      value: "subject",
      fieldname: "subject",
      fieldtype: "Data",
    };

    expect(
      carryOver(
        gone,
        created,
        conditionOperators(created.fieldtype, created.fieldname)
      ).value
    ).not.toBe("Open");

    // Text is what it was, so a text field still takes it.
    expect(
      carryOver(
        gone,
        subject,
        conditionOperators(subject.fieldtype, subject.fieldname)
      ).value
    ).toBe("Open");

    // A Select proves for itself whether the word is one of its options.
    expect(
      carryOver(
        gone,
        status,
        conditionOperators(status.fieldtype, status.fieldname)
      ).value
    ).toBe("Open");
    expect(
      carryOver(
        gone,
        priority,
        conditionOperators(priority.fieldtype, priority.fieldname)
      ).value
    ).not.toBe("Open");
  });

  it("falls back to Filter's own list when the caller names none", () => {
    const prev: Filter = {
      field: status,
      fieldname: "status",
      operator: "is not",
      value: "set",
    };

    expect(carryOver(prev, priority).operator).not.toBe("is not");
  });
});
