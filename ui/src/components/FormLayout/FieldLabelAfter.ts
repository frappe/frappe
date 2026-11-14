import { h, Teleport, type FunctionalComponent, type VNode } from "vue";

/**
 * Draws a field's `label-after` slot inside the control's own label element, after the label's last word.
 * A control without a label (Heading, Button, Html) gets the slot on a line of its own under it.
 */
export const FieldLabelAfter: FunctionalComponent<{ host: Element | null }> = (props, { slots }) => {
  const content = slots.default?.() as VNode[] | undefined;
  if (props.host) return [h(Teleport, { to: props.host }, content)];
  return [h("div", { class: "flex h-5 items-center empty:hidden", "data-slot": "label-after" }, content)];
};

FieldLabelAfter.props = ["host"];
