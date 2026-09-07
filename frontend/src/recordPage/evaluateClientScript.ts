// A stored script is evaluated as a real ES module through a blob URL, so `export
// default {…}` is the same text as a file script and bare imports resolve through the import map.
import type { PageScriptRow } from "./pageScriptTypes";
import type { AuthoredHandlers } from "./types";

export async function evaluatePageScript(
  row: PageScriptRow,
): Promise<AuthoredHandlers> {
  const url = URL.createObjectURL(
    new Blob([named(row)], { type: "text/javascript" }),
  );
  try {
    const module = await import(/* @vite-ignore */ url);
    return handlersOf(module.default);
  } finally {
    // Safe once the import has settled: the module map holds the evaluated
    // module, not the URL.
    URL.revokeObjectURL(url);
  }
}

/** Names the module so stack traces and devtools show the script, not a blob id. */
function named(row: PageScriptRow) {
  return `${row.script}\n//# sourceURL=page-script/${row.name}.js\n`;
}

function handlersOf(handlers: unknown): AuthoredHandlers {
  if (!handlers || typeof handlers !== "object")
    throw new Error("default export is not a handlers object");
  return handlers as AuthoredHandlers;
}
