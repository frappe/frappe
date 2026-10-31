import { describe, expect, it, vi } from "vitest";
import type { RecordPageController } from "@/recordPage";
import { buttonClicks } from "../recordCommits";

function controllerWith(fields: Record<string, string>) {
  const fireEvent = vi.fn();
  const controller = {
    fields: {
      has: (fieldname: string) => fieldname in fields,
      get: (fieldname: string) => ({ fieldname, fieldtype: fields[fieldname] }),
    },
    fireEvent,
  } as unknown as RecordPageController;
  return { controller, fireEvent };
}

function clickOf(fieldname: string, controller: RecordPageController) {
  const ui = buttonClicks(() => controller)({ fieldname, fieldtype: "Button" });
  return ui!.on!.click as (event: MouseEvent, row?: object) => void;
}

describe("buttonClicks", () => {
  it("fires the doctype's own Button by its fieldname", () => {
    const { controller, fireEvent } = controllerWith({ ping: "Button" });
    clickOf("ping", controller)(new MouseEvent("click"));
    expect(fireEvent).toHaveBeenCalledWith("ping");
  });

  it("leaves every other fieldtype plain", () => {
    const { controller } = controllerWith({ title: "Data" });
    expect(buttonClicks(() => controller)({ fieldname: "title", fieldtype: "Data" })).toBeUndefined();
  });

  it("fires nothing for a child row's Button, in a grid cell or the row dialog", () => {
    const { controller, fireEvent } = controllerWith({ ping: "Button", status: "Data" });
    clickOf("ping", controller)(new MouseEvent("click"), { name: "row-1" });
    clickOf("pick_batch", controller)(new MouseEvent("click"));
    clickOf("status", controller)(new MouseEvent("click"));
    expect(fireEvent).not.toHaveBeenCalled();
  });
});
