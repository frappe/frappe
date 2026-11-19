// The module a DocType was last created in, per user, in this browser: the New DocType dialog's first answer.
import { browserMemory } from "@/browserMemory";

export function lastModule(user: string) {
  const memory = browserMemory(
    "newDoctypeModule",
    user,
    (value): value is string => typeof value === "string",
  );
  return {
    recall: () => memory.recall() ?? "",
    remember: (module: string) => memory.remember(module),
  };
}
