/**
 * Self-contained tests for the toast store.
 * Run: cd apps/web && npx tsx src/lib/toast.test.ts
 */
import {
  clear,
  dismiss,
  getToasts,
  push,
  subscribe,
  type Toast,
} from "../hooks/useToast";

let passed = 0;
let failed = 0;

function assert(condition: boolean, msg: string): void {
  if (condition) {
    passed++;
  } else {
    failed++;
    console.error(`  FAIL: ${msg}`);
  }
}

function assertEqual(actual: unknown, expected: unknown, msg: string): void {
  if (actual === expected) {
    passed++;
  } else {
    failed++;
    console.error(`  FAIL: ${msg} — expected ${String(expected)}, got ${String(actual)}`);
  }
}

// ---------------------------------------------------------------------------
// Test: subscribe receives initial state, then updates on push
// ---------------------------------------------------------------------------
clear();
let received: readonly Toast[] = [];
const unsub = subscribe((t) => {
  received = t;
});
assertEqual(received.length, 0, "subscribe emits initial empty state");

const id = push({ variant: "success", title: "hi", duration: 0 });
assertEqual(received.length, 1, "subscribe receives update after push");
assertEqual(received[0]?.title, "hi", "push preserves title");
assertEqual(received[0]?.id, id, "push returns new toast id");
assertEqual(received[0]?.variant, "success", "push preserves variant");

// ---------------------------------------------------------------------------
// Test: dismiss removes only matching id
// ---------------------------------------------------------------------------
const id2 = push({ variant: "error", title: "boom", duration: 0 });
assertEqual(received.length, 2, "second push appends");
dismiss(id);
assertEqual(received.length, 1, "dismiss removes target toast");
assertEqual(received[0]?.id, id2, "remaining toast is the other id");
dismiss("nonexistent");
assertEqual(received.length, 1, "dismiss with unknown id is a no-op");

// ---------------------------------------------------------------------------
// Test: ID monotonicity after clear resets counter
// ---------------------------------------------------------------------------
clear();
assertEqual(received.length, 0, "clear empties toasts");
const a = push({ variant: "info", title: "a", duration: 0 });
const b = push({ variant: "info", title: "b", duration: 0 });
assert(a !== b, "sequential pushes have distinct ids");
assert(Number(b) > Number(a), "ids are monotonically increasing");
assertEqual(a, "1", "clear resets id counter");

// ---------------------------------------------------------------------------
// Test: unsubscribe stops notifications
// ---------------------------------------------------------------------------
clear();
let count = 0;
const un = subscribe(() => {
  count++;
});
assertEqual(count, 1, "subscribe fires once on registration");
un();
push({ variant: "info", title: "x", duration: 0 });
assertEqual(count, 1, "unsubscribed listener does not fire on push");

// ---------------------------------------------------------------------------
// Test: multiple listeners all receive updates
// ---------------------------------------------------------------------------
clear();
let aCount = 0;
let bCount = 0;
const unA = subscribe(() => {
  aCount++;
});
const unB = subscribe(() => {
  bCount++;
});
push({ variant: "info", title: "m", duration: 0 });
assertEqual(aCount, 2, "listener A fired on register + push");
assertEqual(bCount, 2, "listener B fired on register + push");
unA();
unB();

// ---------------------------------------------------------------------------
// Test: getToasts returns current state
// ---------------------------------------------------------------------------
clear();
assertEqual(getToasts().length, 0, "getToasts reflects empty state");
push({ variant: "success", title: "ok", duration: 0 });
assertEqual(getToasts().length, 1, "getToasts reflects current state");

unsub();
clear();

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
} else {
  console.log("OK");
}
