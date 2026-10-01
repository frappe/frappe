// The acts a script makes in a replay or a hold, kept back until the last of them commits.

/** Why a held act is dropped when the first paint goes ahead without its target. */
export const NOT_DRAWN = "the first paint went ahead without it";

/** Why an act is dropped when it runs in the replay after a background read. */
export const IN_BACKGROUND = "it ran in the replay after a background read";

/** The order held acts land in, whatever order a script called them in. */
export const LANDING_ORDER = ["activate", "disclose", "focus", "scrollTo", "open"] as const;

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

export interface HeldActsHost {
  isStaging: () => boolean;
  inBackground: () => boolean;
}

export function createHeldActs(host: HeldActsHost) {
  const held = new Map<string, HeldAct>();

  /** Holds or drops the act and answers true; false means the caller delivers it now. */
  function take(act: HeldAct) {
    if (host.inBackground()) act.refuse(IN_BACKGROUND);
    else if (host.isStaging()) held.set(`${act.kind}:${act.target}`, act);
    else return false;
    return true;
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

  return { take, release };
}

function byLandingOrder(a: HeldAct, b: HeldAct) {
  return LANDING_ORDER.indexOf(a.kind) - LANDING_ORDER.indexOf(b.kind);
}
