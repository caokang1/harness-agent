/**
 * Condition-based waiting: complete example.
 *
 * Companion to condition-based-waiting.md. Flaky tests were sleeping for a
 * guessed number of milliseconds and then asserting on an event log, e.g.
 *
 *   await new Promise(r => setTimeout(r, 300)); // hope the tool finished
 *   expect(manager.getEvents().some(e => e.type === 'TOOL_RESULT')).toBe(true);
 *
 * which passes on a fast laptop and fails under CI load. The helpers below
 * poll for the condition the test actually cares about, return as soon as it
 * holds, and fail with a descriptive message if it never does.
 *
 * Self-contained: the "event source" is a minimal interface so the helpers
 * can be copied into any project that records events (an agent/thread
 * manager, an event bus, a mock server, ...).
 */

// ---------------------------------------------------------------------------
// Domain types (minimal stand-ins for your project's real types)
// ---------------------------------------------------------------------------

export type EventType =
  | 'USER_MESSAGE'
  | 'AGENT_MESSAGE'
  | 'TOOL_STARTED'
  | 'TOOL_PROGRESS'
  | 'TOOL_RESULT'
  | 'ERROR'
  | 'DONE';

export interface RecordedEvent<TData = unknown> {
  type: EventType;
  data?: TData;
  timestamp: number;
}

/** Anything that exposes its recorded events. Read FRESH on every poll. */
export interface EventSource {
  getEvents(): ReadonlyArray<RecordedEvent>;
}

// ---------------------------------------------------------------------------
// Generic helper
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 10; // Fast enough for tests, slow enough not to burn CPU
const DEFAULT_TIMEOUT_MS = 5000;

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Poll `condition` until it returns a truthy value, then return that value.
 * Throws `Timeout waiting for <description> after <timeoutMs>ms` otherwise.
 *
 * The condition is a function (not a value) so state is re-read on every
 * iteration -- caching state before the loop is a classic mistake.
 */
export async function waitFor<T>(
  condition: () => T | undefined | null | false,
  description: string,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const startTime = Date.now();

  while (true) {
    const result = condition();
    if (result) return result;

    if (Date.now() - startTime > timeoutMs) {
      throw new Error(`Timeout waiting for ${description} after ${timeoutMs}ms`);
    }

    await sleep(POLL_INTERVAL_MS);
  }
}

// ---------------------------------------------------------------------------
// Domain-specific helpers
// ---------------------------------------------------------------------------

function describeEvents(source: EventSource): string {
  const types = source.getEvents().map((e) => e.type);
  return types.length ? types.join(', ') : '(none)';
}

/** Wrap a waitFor call so timeout errors also show which events DID arrive. */
async function withEventContext<T>(source: EventSource, wait: Promise<T>): Promise<T> {
  try {
    return await wait;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(`${message}. Events seen so far: ${describeEvents(source)}`);
  }
}

/**
 * Wait for the first event of the given type and return it.
 *
 *   const started = await waitForEvent(manager, 'TOOL_STARTED');
 */
export function waitForEvent(
  source: EventSource,
  eventType: EventType,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<RecordedEvent> {
  return withEventContext(
    source,
    waitFor(() => source.getEvents().find((e) => e.type === eventType), `${eventType} event`, timeoutMs)
  );
}

/**
 * Wait until at least `count` events of the given type exist; return them.
 *
 *   const msgs = await waitForEventCount(manager, 'AGENT_MESSAGE', 2);
 */
export function waitForEventCount(
  source: EventSource,
  eventType: EventType,
  count: number,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<RecordedEvent[]> {
  return withEventContext(
    source,
    waitFor(
      () => {
        const matching = source.getEvents().filter((e) => e.type === eventType);
        return matching.length >= count ? matching : undefined;
      },
      `${count} ${eventType} events`,
      timeoutMs
    )
  );
}

/**
 * Wait for the first event satisfying an arbitrary predicate.
 *
 *   const result = await waitForEventMatch(
 *     manager,
 *     (e) => e.type === 'TOOL_RESULT' && (e.data as { id?: string })?.id === 'call_1',
 *     'TOOL_RESULT for call_1'
 *   );
 */
export function waitForEventMatch(
  source: EventSource,
  predicate: (event: RecordedEvent) => boolean,
  description: string,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<RecordedEvent> {
  return withEventContext(
    source,
    waitFor(() => source.getEvents().find(predicate), description, timeoutMs)
  );
}

// ---------------------------------------------------------------------------
// Usage examples
// ---------------------------------------------------------------------------

/** Tiny fake event source that emits events asynchronously, like a real agent. */
export class FakeManager implements EventSource {
  private events: RecordedEvent[] = [];

  getEvents(): ReadonlyArray<RecordedEvent> {
    return this.events;
  }

  emit(type: EventType, data?: unknown, delayMs = 0): void {
    setTimeout(() => this.events.push({ type, data, timestamp: Date.now() }), delayMs);
  }

  /** Simulates a tool run whose duration varies with machine load. */
  runTool(id: string, ticks: number, tickMs = 100): void {
    this.emit('TOOL_STARTED', { id }, 5);
    for (let i = 1; i <= ticks; i++) this.emit('TOOL_PROGRESS', { id, tick: i }, 5 + i * tickMs);
    this.emit('TOOL_RESULT', { id, ok: true }, 10 + ticks * tickMs);
    this.emit('DONE', undefined, 15 + ticks * tickMs);
  }
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`Assertion failed: ${message}`);
}

/** Example test bodies showing BEFORE (flaky) vs AFTER (condition-based). */
export async function examples(): Promise<void> {
  // ❌ BEFORE: guessing at timing -- fails whenever the tool takes > 250ms.
  //   manager.runTool('call_1', 2);
  //   await new Promise(r => setTimeout(r, 250));
  //   assert(manager.getEvents().some(e => e.type === 'TOOL_RESULT'), 'tool finished');

  // ✅ AFTER: wait for the actual condition.
  const manager = new FakeManager();
  manager.runTool('call_1', 2);

  const result = await waitForEvent(manager, 'TOOL_RESULT');
  assert((result.data as { ok?: boolean }).ok === true, 'tool result ok');

  // Wait for a count of events.
  const progress = await waitForEventCount(manager, 'TOOL_PROGRESS', 2);
  assert(progress.length >= 2, 'two progress ticks');

  // Wait for a specific event matching a predicate.
  const second = await waitForEventMatch(
    manager,
    (e) => e.type === 'TOOL_PROGRESS' && (e.data as { tick?: number }).tick === 2,
    'second TOOL_PROGRESS tick'
  );
  assert(second.timestamp > 0, 'tick has timestamp');

  // Generic waitFor on arbitrary state.
  await waitFor(() => manager.getEvents().some((e) => e.type === 'DONE'), 'DONE event');

  // When an arbitrary timeout IS correct: testing timed behaviour itself.
  const ticking = new FakeManager();
  ticking.runTool('call_2', 3);
  await waitForEvent(ticking, 'TOOL_STARTED'); // First: wait for the triggering condition
  await sleep(200); // Then: wait for timed behaviour
  // 200ms = 2 ticks at 100ms intervals - documented and justified
  const ticksSoFar = ticking.getEvents().filter((e) => e.type === 'TOOL_PROGRESS').length;
  assert(ticksSoFar >= 1, 'partial progress observed mid-run');

  // A timeout fails loudly with context instead of hanging forever.
  try {
    await waitForEvent(manager, 'ERROR', 100);
    throw new Error('expected timeout');
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    assert(message.startsWith('Timeout waiting for ERROR event after 100ms'), 'descriptive timeout');
  }
}
