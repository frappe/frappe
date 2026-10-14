// A mounted component under a memory router, so rows can render as links.
import { createApp, h, nextTick } from "vue";
import type { Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

const mounted: ReturnType<typeof createApp>[] = [];

export function unmountAll() {
  for (const app of mounted.splice(0)) app.unmount();
  document.body.innerHTML = "";
}

export async function mount(
  component: Component,
  props: Record<string, unknown> = {},
  slots: Record<string, () => unknown> = {}
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:pathMatch(.*)*", component: { render: () => null } }],
  });
  await router.push("/");
  await router.isReady();

  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp({ render: () => h(component, { ...props }, slots) });
  app.use(router);
  app.mount(root);
  mounted.push(app);
  await nextTick();

  return { root, router };
}

export async function flush() {
  await Promise.resolve();
  await nextTick();
}
