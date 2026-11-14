import { h, Teleport, type FunctionalComponent, type VNode } from "vue";

/** Appends marks to the control's label, or draws them below a label-less control. */
export const FieldLabelAfter: FunctionalComponent<{ host: Element | null }> = (props, { slots }) => {
  const content = slots.default?.() as VNode[] | undefined;
  if (props.host) return [h(Teleport, { to: props.host }, content)];
  return [h("div", { class: "flex h-5 items-center empty:hidden", "data-slot": "label-after" }, content)];
};

FieldLabelAfter.props = ["host"];
