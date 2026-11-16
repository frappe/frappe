# A field error is display-only

A field control can show an error under its input. The error never refuses a
save. Only a save-time check refuses a save: the mandatory check, or a
`beforeSave` that throws.

## How an error reaches a control

Every control takes an optional `error` prop (`string | string[]`) and passes it
to its frappe-ui atom, the same way it passes `field.reqd`. The Code family has
no atom that takes `error`, so it draws the error with frappe-ui's
`ErrorMessage`. A control never sets an error itself.

The host owns one reactive map and provides it through `FieldErrorsKey`. The map
key comes from `fieldErrorKey(address)`:

```ts
import { FieldErrorsKey, fieldErrorKey } from "@framework/ui/fields";
import type { FieldError } from "@framework/ui/fields";

const errors = ref<Record<string, FieldError>>({});
provide(FieldErrorsKey, errors);

errors.value = {
  [fieldErrorKey("customer")]: "Customer is required",
  [fieldErrorKey({ parentfield: "items", key: "name:row-1", fieldname: "qty" })]:
    "Qty must be positive",
};
```

The row key is the one the commit channel already carries (`RowAddress.key`). A host
with no form (a filter, a dialog inside a form) provides `null`, and nothing is drawn.

- `FormLayoutField` reads the error for its fieldname and passes it to the control.
- A grid cell does not pass `error` to its control, because the message would make
  the row taller. The cell draws a red ring and shows the message as a tooltip.
- The row-edit dialog passes each of its row's errors to the control for that field.
- Button, Heading, HTML and Image hold no value, so no check can name them. They
  take the prop and draw nothing.

## Why an error does not block

A blocking error goes stale. A server error stays after the reader edits a
related field. A script error stays on a field that `depends_on` now hides. In
both cases the reader cannot save, and has nothing to click to fix it.

A save-time check does not go stale, because it runs on the document as it is at
save. So a script that must refuse a save throws from `beforeSave`, and a host
that marks the field as well sets its error before it throws.
