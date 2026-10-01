// The acts a script makes in a replay or a hold, kept back until the last of them commits.

/** Why a held act is dropped when the first paint goes ahead without its target. */
const NOT_DRAWN = "the first paint went ahead without it";

/** Why an act is dropped when it runs in the replay after a background read. */
const IN_BACKGROUND = "it ran in the replay after a background read";

/** The order held acts land in, whatever order a script called them in. */
const LANDING_ORDER = ["activate", "disclose", "focus", "scrollTo", "open"] as const;

/** One act a script made; for one kind and target, the last one held wins. */
export interface HeldAct {
  kind: (typeof LANDING_ORDER)[number];
  /** The strip for an activation, the section for a disclosure, else "". */
  target: string;
  isDrawn(): boolean;
  /** Reads the target again and delivers. */
  land(): void;
  refuse(because: string): void;
}

/** What `take` did with an act; false means the caller delivers it now. */
export type TakeResult = false | "held" | "dropped";

export interface HeldActsHost {
  isStaging: () => boolean;
  inBackground: () => boolean;
}

export function createHeldActs(host: HeldActsHost) {
  const held = new Map<string, HeldAct>();

  /** Drops the act in a background replay, holds it in any other replay or hold. */
  function take(act: HeldAct): TakeResult {
    if (host.inBackground()) {
      act.refuse(IN_BACKGROUND);
      return "dropped";
    }
    if (!host.isStaging()) return false;
    held.set(keyOf(act.kind, act.target), act);
    return "held";
  }

  /** Removes a held act at once, in a background replay as in a hold. */
  function drop(kind: HeldAct["kind"], target: string) {
    held.delete(keyOf(kind, target));
  }

  /** Lands every held act; `drawnOnly` drops one whose target is not drawn. */
  function release(drawnOnly: boolean) {
    const acts = [...held.values()].sort(byLandingOrder);
    held.clear();
    for (const act of acts) {
      if (drawnOnly && !act.isDrawn()) act.refuse(NOT_DRAWN);
      else act.land();
    }
  }

  return { take, drop, release };
}

function byLandingOrder(a: HeldAct, b: HeldAct) {
  return LANDING_ORDER.indexOf(a.kind) - LANDING_ORDER.indexOf(b.kind);
}

function keyOf(kind: HeldAct["kind"], target: string) {
  return `${kind}:${target}`;
}
