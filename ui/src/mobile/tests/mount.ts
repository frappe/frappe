import { createApp, h, nextTick } from "vue";
import type { Component } from "vue";

const mounted: ReturnType<typeof createApp>[] = [];

export function unmountAll() {
  for (const app of mounted.splice(0)) app.unmount();
  document.body.innerHTML = "";
}

export async function mount(
  component: Component,
  props: Record<string, unknown> = {},
  slots: Record<string, (scope: any) => unknown> = {}
) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp({ render: () => h(component, props, slots) });
  app.mount(root);
  mounted.push(app);
  await nextTick();
  return root;
}

export const rows = (root: HTMLElement) =>
  Array.from(root.querySelectorAll<HTMLElement>("[data-slot=list-row]"));
