// The header finder opens a collapsed group of the field panel before it flashes a row.
import { afterEach, expect, it } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";
import {
  activePanel,
  providePanelIndex,
  revealProperty,
  usePanelGroup,
  usePanelRow,
} from "../panelIndex";

let app: App | undefined;
afterEach(() => {
  app?.unmount();
  app = undefined;
  document.body.innerHTML = "";
});

it("opens the collapsed group a picked row sits in", async () => {
  const open = ref(false);
  const Row = defineComponent({
    setup() {
      usePanelRow(
        () => "Hidden",
        () => null,
      );
      return () => h("div");
    },
  });
  const Group = defineComponent({
    setup() {
      usePanelGroup(() => "Display", open);
      return () => h(Row);
    },
  });
  const Panel = defineComponent({
    setup() {
      providePanelIndex();
      return () => h(Group);
    },
  });
  app = createApp(Panel);
  app.mount(document.body.appendChild(document.createElement("div")));
  await nextTick();

  const index = activePanel.value!;
  const row = [...index.rows.values()][0];
  expect(index.groups.get(row.group)?.label).toBe("Display");
  await revealProperty(index, row);
  expect(open.value).toBe(true);
});
