// `/doctype/new` without its answers: the New DocType dialog opens over the DocType list, and
// Continue opens the editor on what it asked.
import { toast } from "frappe-ui";
import { isNavigationFailure, type Router } from "vue-router";
import { __ } from "@/i18n";
import { COPY_OF } from "@/newRecordValues";
import { errorMessage } from "@/recordPage/errorMessage";
import { routeFor, routeForNew } from "@/router/routeFor";
import { shellDialog } from "@/shell/dialog";
import type { NewDoctype } from "./editorSource";
import { lastModule } from "./lastModule";

export async function askNewDoctype(
  router: Router,
  initial: Partial<NewDoctype>,
  copyOf: string | null,
  user: string,
) {
  try {
    await ask(router, initial, copyOf, user);
  } catch (error) {
    toast.error(errorMessage(error));
  }
}

async function ask(
  router: Router,
  initial: Partial<NewDoctype>,
  copyOf: string | null,
  user: string,
) {
  // A failed replace leaves the editor's own route: the dialog must not open over it.
  if (isNavigationFailure(await router.replace(routeFor("DocType")))) return;
  const { default: NewDoctypeDialog } = await import("./NewDoctypeDialog.vue");
  const remembered = lastModule(user).recall();
  const props = { initial: { module: remembered, ...initial }, remembered };
  const answers: NewDoctype | null = await shellDialog().open(
    NewDoctypeDialog,
    props,
    { title: __("New DocType") },
  );
  if (!answers) return;
  await router.push(
    routeForNew("DocType", {
      ...answers,
      custom: answers.custom ? 1 : 0,
      [COPY_OF]: copyOf,
    }),
  );
}
