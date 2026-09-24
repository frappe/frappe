// Orders replies by the time their request was sent, per document and per list.
// A ticket is taken at send time; the counter never restarts, so a sealed document stays sealed.

export class WriteGate {
  private counter = 0;
  private floor = 0;
  private applied = new Map<string, number>();
  private sealed = new Set<string>();
  private landed = new Map<string, number>();
  private listed = new Map<string, number>();

  next(): number {
    return ++this.counter;
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
  }
}
