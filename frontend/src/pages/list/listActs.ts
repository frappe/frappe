// The list page's one act surface, `list`: its built-ins as named acts, which its buttons and menu draw.
import { toast } from "frappe-ui";
import { onScopeDispose } from "vue";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useSession } from "@framework/ui/useSession";
import {
  acts,
  type ActEntry,
  type ActRight,
  type AvailableAct,
} from "@/acts/dispatcher";
import { useCreateRight } from "@/createRight";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import { whenLoaded } from "@/recordPage/pagePermissions";

export interface ListActsHost {
  doctype: string;
  create: () => unknown;
  customizeQuickFilter: () => void;
  confirmDelete: () => void;
  customizing: () => boolean;
  selected: () => number;
}

export interface ListActs {
  /** The act by its item name while the dispatcher would run it, so the page draws it. */
  drawn: (name: string) => AvailableAct | undefined;
  perform: (act: AvailableAct) => void;
}

/** Registers the `list` surface for the page's life; the page draws its controls from `drawn`. */
export function useListActs(host: ListActsHost): ListActs {
  const passes = useListRight(host.doctype);
  const { loading } = useDocPermissions(host.doctype);
  const release = acts.register({
    surfaces: { list: () => listEntries(host) },
    context: () => undefined,
    passes,
    settled: () => (loading.value ? whenLoaded(loading) : undefined),
    hold: async (work) => work(),
    failed: (error) => void toast.error(errorMessage(error)),
  });
  onScopeDispose(release);

  return {
    drawn: (name) =>
      acts.available().find((act) => act.name === `list.${name}`),
    perform: (act) => void acts.perform(act.name),
  };
}

function listEntries(host: ListActsHost): ActEntry[] {
  const entries: ActEntry[] = [
    {
      item: {
        name: "create",
        label: __("Create"),
        icon: "lucide-plus",
        right: "create",
        run: () => host.create(),
      },
      hidden: false,
    },
    {
      item: {
        name: "customize_quick_filter",
        label: __("Customize Quick Filter"),
        icon: "lucide-sliders-horizontal",
        run: () => host.customizeQuickFilter(),
      },
      hidden: host.customizing(),
    },
  ];
  if (host.selected() > 0)
    entries.push({
      item: {
        name: "delete",
        label: __("Delete"),
        icon: "lucide-trash-2",
        right: "delete",
        run: () => host.confirmDelete(),
      },
      hidden: false,
    });
  return entries;
}

/** A right on the list's doctype; its create right is the list's Create rule. */
function useListRight(doctype: string): (right: ActRight) => boolean {
  const canCreate = useCreateRight(doctype);
  const { holds } = useDocPermissions(doctype);
  const { session } = useSession();
  return (right) => {
    if (typeof right !== "string") return false;
    if (right === "create") return canCreate.value;
    return session.value?.user.name === "Administrator" || holds(right);
  };
}
