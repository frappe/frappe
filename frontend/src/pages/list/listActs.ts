// The list page's one act surface, `list`: its built-ins as named acts, which its buttons and menu draw.
import { toast } from "frappe-ui";
import { onScopeDispose } from "vue";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useSession } from "@framework/ui/useSession";
import {
  acts,
  type ActEntry,
  type ActItem,
  type ActRight,
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
  /** The built-in by item name while the page draws it: present, shown, and its right passes. */
  drawn: (name: string) => ActItem | undefined;
  perform: (name: string) => void;
}

/** Registers the `list` surface for the page's life; the page draws its controls from `drawn`. */
export function useListActs(host: ListActsHost): ListActs {
  const rights = new ListRights(host.doctype);
  const entries = () => listEntries(host);
  const release = acts.register({
    surfaces: { list: entries },
    context: () => undefined,
    passes: (right) => rights.passes(right),
    settled: (right) => rights.settled(right),
    hold: async (work) => work(),
    failed: (error) => void toast.error(errorMessage(error)),
  });
  onScopeDispose(release);

  return {
    drawn: (name) => {
      const entry = entries().find(({ item }) => item.name === name);
      if (!entry || entry.hidden) return undefined;
      return !entry.item.right || rights.passes(entry.item.right)
        ? entry.item
        : undefined;
    },
    perform: (name) => void acts.perform(`list.${name}`),
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

/** A right on the list's doctype, or on another; the create right is the list's Create rule. */
class ListRights {
  private canCreate;
  private own;
  private session = useSession().session;

  constructor(private doctype: string) {
    this.canCreate = useCreateRight(doctype);
    this.own = useDocPermissions(doctype);
  }

  passes(right: ActRight): boolean {
    const { doctype, ptype } = this.rightOn(right);
    if (doctype !== this.doctype)
      return useDocPermissions(doctype).holds(ptype);
    if (ptype === "create") return this.canCreate.value;
    return (
      this.session.value?.user.name === "Administrator" || this.own.holds(ptype)
    );
  }

  settled(right: ActRight): Promise<void> | undefined {
    const { doctype } = this.rightOn(right);
    const { loading } =
      doctype === this.doctype ? this.own : useDocPermissions(doctype);
    return loading.value ? whenLoaded(loading) : undefined;
  }

  private rightOn(right: ActRight) {
    return typeof right === "string"
      ? { doctype: this.doctype, ptype: right }
      : right;
  }
}
