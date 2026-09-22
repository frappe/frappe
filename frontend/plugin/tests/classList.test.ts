import { describe, expect, it } from "vitest";
import classList, { CLASS_LIST, classNames } from "../classList.js";

describe("the class list the build writes for the server", () => {
  it("reads every class selector, unescaped, once", () => {
    expect(
      classNames(
        String.raw`.p-3{padding:.75rem}.p-3:hover{}.hover\:bg-x:hover{}.\32xl\:flex{}.w-1\/2{}.\31 0{}a.b .c>.d{}`,
      ),
    ).toEqual(["p-3", "hover:bg-x", "2xl:flex", "w-1/2", "10", "b", "c", "d"]);
  });

  it("emits classes.json from every stylesheet in the bundle, sorted", () => {
    const emitted: any[] = [];
    const plugin = classList() as any;
    plugin.generateBundle.call(
      { emitFile: (file: any) => emitted.push(file) },
      {},
      {
        "assets/index-1.css": {
          type: "asset",
          fileName: "assets/index-1.css",
          source: ".p-3{}.flex{}",
        },
        "assets/Button-1.css": {
          type: "asset",
          fileName: "assets/Button-1.css",
          source: ".flex{}.rounded-4{}",
        },
        "assets/index-1.js": {
          type: "chunk",
          fileName: "assets/index-1.js",
          code: ".not-a-class{}",
        },
      },
    );
    expect(emitted).toEqual([
      {
        type: "asset",
        fileName: CLASS_LIST,
        source: JSON.stringify(["flex", "p-3", "rounded-4"]),
      },
    ]);
  });

  it("writes an empty list when the bundle has no stylesheet", () => {
    const emitted: any[] = [];
    (classList() as any).generateBundle.call(
      { emitFile: (file: any) => emitted.push(file) },
      {},
      {},
    );
    expect(JSON.parse(emitted[0].source)).toEqual([]);
  });
});
