import { defineComponent, h, ref } from "vue";

// The real menus open in a portal on pointer events; these stubs draw their items
// as buttons. The context menu's items show once a right-click reaches its trigger.
const items = (options: any[]) =>
  options.map((o) => h("button", { "data-menu-item": o.label, onClick: o.onClick }, o.label));

export const Dropdown = defineComponent({
  props: ["options"],
  setup: (props, { slots }) => () =>
    h("div", { "data-dropdown": "" }, [slots.default?.(), ...items(props.options)]),
});

export const ContextMenu = defineComponent({
  props: ["options"],
  setup(props, { slots }) {
    const open = ref(false);
    return () =>
      h("div", { onContextmenu: () => (open.value = true) }, [
        slots.default?.(),
        open.value ? h("div", { "data-context-menu": "" }, items(props.options)) : null,
      ]);
  },
});
