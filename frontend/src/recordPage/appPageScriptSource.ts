// The app page scripts the builder runs: `main.ts` hands this over with `setAppPageScripts`.
import type { AppPageScriptSource } from "@/pageEngine/appPageScripts";
import {
  clientScriptChanges,
  clientScriptsLoaded,
  clientScriptWait,
  loadClientScripts,
  replacedClientScripts,
} from "./clientScripts";
import { pageScriptsFor } from "./pageScripts";

export const appPageScriptSource: AppPageScriptSource = {
  sources: pageScriptsFor,
  load: loadClientScripts,
  loaded: clientScriptsLoaded,
  replaced: replacedClientScripts,
  wait: clientScriptWait,
  changes: clientScriptChanges,
};
