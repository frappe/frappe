// The complete records, least recently read first, each with the size of the reply that made it complete.
interface RecordLimits {
  count: number;
  replySize: number;
}

export class CompleteRecords {
  private sizes = new Map<string, number>();
  private total = 0;

  constructor(private readonly limits: RecordLimits) {}

  keys(): IterableIterator<string> {
    return this.sizes.keys();
  }

  visit(key: string, replySize: number): void {
    this.delete(key);
    this.sizes.set(key, replySize);
    this.total += replySize;
  }

  delete(key: string): void {
    this.total -= this.sizes.get(key) ?? 0;
    this.sizes.delete(key);
  }

  clear(): void {
    this.sizes.clear();
    this.total = 0;
  }

  /** The least recently read record while either limit is passed; never the last one read, the open record. */
  nextToDrop(): string | undefined {
    const within = this.sizes.size <= this.limits.count && this.total <= this.limits.replySize;
    if (within || this.sizes.size <= 1) return undefined;
    return this.sizes.keys().next().value;
  }
}
