// `header.assign`, the `⋯` menu's "Assign to…": its argument step lists users, the assigned ones marked.
import type { ActOption } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { HeaderItem, RecordPageApi } from "@/recordPage";
import type { Person } from "./panel/people";
import { findUsers } from "./panel/remoteSearch";

/** Who the record is assigned to now, and the write that adds one more. */
export interface AssignState {
  assignees: Person[];
  assign: (page: RecordPageApi, user: string) => unknown;
}

export function assignItem(state: AssignState): HeaderItem {
  return {
    name: "assign",
    label: __("Assign to…"),
    icon: "lucide-user-plus",
    group: "assign_band",
    right: "write",
    argument: {
      label: __("Users"),
      options: (_page: RecordPageApi, query: string) => assignOptions(state.assignees, query),
    },
    run: (page, user?: string) => (user ? state.assign(page, user) : page.toast.error(__("Pick a user to assign"))),
  };
}

/** The server's matches, then the assignees it did not return; an assignee cannot be picked again. */
export async function assignOptions(assignees: Person[], query: string): Promise<ActOption[]> {
  const found = await findUsers(query);
  const assigned = new Map(assignees.map((person) => [person.id, person]));
  const options = found.map((row) => userOption(row.value, nameOf(row), assigned.get(row.value)));
  const listed = new Set(found.map(({ value }) => value));
  for (const person of assignees) if (!listed.has(person.id)) options.push(userOption(person.id, person.name, person));
  return options;
}

// With User's title shown in link fields, the search puts the full name in `label` and drops `description`.
function nameOf({ value, label, description }: { value: string; label?: string; description?: string }) {
  return label && label !== value ? label : description || value;
}

function userOption(user: string, name: string, assignee?: Person): ActOption {
  const option: ActOption = { value: user, label: name, image: assignee?.image ?? null };
  if (name !== user) option.description = user;
  if (assignee) option.disabled = __("Assigned");
  return option;
}
