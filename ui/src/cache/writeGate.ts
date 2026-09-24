// Orders replies by the time their request was sent, per document and per list.
// A ticket is taken at send time; the counter never restarts, so a sealed document stays sealed.

export interface LiveEntries {
  hasDocument(key: string): boolean;
  hasList(key: string): boolean;
}

export class WriteGate {
  private counter = 0;
  private floor = 0;
  private applied = new Map<string, number>();
  private sealed = new Set<string>();
  private landed = new Map<string, number>();
  private listed = new Map<string, number>();
  // Taken in ticket order, so the first is the oldest.
  private inFlight = new Set<number>();
  private retiringDocuments = new Set<string>();
  private retiringLists = new Set<string>();

  constructor(private live: LiveEntries) {}

  next(): number {
    this.inFlight.add(++this.counter);
    return this.counter;
  }

  /** The request sent at `ticket` answered or failed, and its reply has been fed. */
  settle(ticket: number): void {
    this.inFlight.delete(ticket);
    for (const key of this.retiringDocuments) this.retireDocument(key);
    for (const key of this.retiringLists) this.retireList(key);
  }

  documentLeft(key: string): void {
    this.landed.delete(key);
    this.retiringDocuments.add(key);
    this.retireDocument(key);
  }

  listLeft(key: string): void {
    this.retiringLists.add(key);
    this.retireList(key);
  }

  /** False for a request sent before the last clear. */
  current(ticket: number): boolean {
    return ticket > this.floor;
  }

  /** A read records nothing: a later read may land before an earlier save commits. */
  admitRead(key: string, ticket: number): boolean {
    return this.current(ticket) && ticket >= (this.applied.get(key) ?? 0);
  }

  admitWrite(key: string, ticket: number): boolean {
    if (!this.admitRead(key, ticket)) return false;
    this.applied.set(key, ticket);
    this.sealed.delete(key);
    this.retiringDocuments.add(key);
    return true;
  }

  /** False for a list reply sent before the one the list entry holds. */
  admitList(key: string, ticket: number): boolean {
    if (ticket < (this.listed.get(key) ?? 0)) return false;
    this.listed.set(key, ticket);
    return true;
  }

  /** A fresh number: a request still in flight when the delete settles was answered before it. */
  seal(key: string): void {
    this.applied.set(key, ++this.counter);
    this.sealed.add(key);
    this.retiringDocuments.add(key);
  }

  isSealed(key: string): boolean {
    return this.sealed.has(key);
  }

  /** Whether a write sent after `ticket` landed with no delete since. */
  writtenAfter(key: string, ticket: number): boolean {
    return !this.sealed.has(key) && (this.applied.get(key) ?? 0) > ticket;
  }

  /** Records a reply applied to the document's entry. */
  land(key: string, ticket: number): void {
    this.landed.set(key, Math.max(ticket, this.landed.get(key) ?? 0));
  }

  /** Whether a request sent at `ticket` is newer than every reply the entry holds. */
  newerThanEntry(key: string, ticket: number): boolean {
    return ticket > (this.landed.get(key) ?? 0);
  }

  clear(): void {
    this.floor = this.counter;
    this.applied.clear();
    this.sealed.clear();
    this.landed.clear();
    this.listed.clear();
    this.retiringDocuments.clear();
    this.retiringLists.clear();
  }

  /** For tests: how many keys each record holds. */
  sizes() {
    const { applied, sealed, landed, listed } = this;
    return { applied: applied.size, sealed: sealed.size, landed: landed.size, listed: listed.size };
  }

  private retireDocument(key: string): void {
    if (this.live.hasDocument(key)) {
      this.retiringDocuments.delete(key);
    } else if (this.refusesNothing(this.applied.get(key))) {
      this.applied.delete(key);
      this.sealed.delete(key);
      this.retiringDocuments.delete(key);
    }
  }

  private retireList(key: string): void {
    if (this.live.hasList(key)) {
      this.retiringLists.delete(key);
    } else if (this.refusesNothing(this.listed.get(key))) {
      this.listed.delete(key);
      this.retiringLists.delete(key);
    }
  }

  /** A recorded ticket refuses only replies sent before it. */
  private refusesNothing(recorded = 0): boolean {
    const oldest = this.inFlight.values().next().value;
    return oldest === undefined || recorded < oldest;
  }
}
