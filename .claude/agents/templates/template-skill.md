---
name: development
description: Provides development tools and guidance. Use when developing code, debugging, or running anything in the development environment.
---

# Development

## Technology Stack

- Node.js app with web interface using Remix
- Docker containerized

## Development Guidelines

Main scripts:

- Lint: `yarn lint`
- Test: `yarn test`
- Debug server: `yarn dev`
- Build: `yarn build`

## Running Dev

Environment variable `$PORT` defines the Vite server port.

Checking if server is up:

```bash
lsof -ti :$PORT
```

Killing to restart a server, if occupied:

```bash
kill `lsof -ti :$PORT`
```

### Debugging with yarn dev

This application does not have Hot Module Reload enabled. When you are about to give `<reproduction_steps>` during debugging, do this first so the user never tests on a stale server:

1. **Ensure server is closed** - `lsof -ti :3001 | xargs -r kill`
2. **Start dev** - `yarn dev` in background.
3. **Sleep ~65 seconds** - dev needs time to spin up (services).
4. **Then** output your `<reproduction_steps>`.

This avoids wrong conclusions from testing against an old process.

### Terminal Only Dev Test

Command: `TEST_ONLY=true yarn dev` *(don't background it)*

Use when running a specific server function and tearing down in one move.

### @Browser Dev Server

Command: `yarn dev` *(background it)*

Use when running dev for @browser automation or when you want the user to test something.

## Debugging Approach

When debugging issues, follow this systematic approach to avoid drowning the codebase in unnecessary logging.

### 1. Hypothesize First

Before adding any instrumentation, state 3-5 concrete, testable hypotheses. Good ones are specific and testable (e.g. "the auth token is null at checkout" or "the loop uses `count < 10` instead of `count <= 10`"). Avoid vague statements ("something is broken in the payment flow").

### 2. Instrument to Test Hypotheses

Write debug lines to `.cursor/debug-{sessionId}.log` (server: `fs.appendFileSync`; client: POST to `/debug/ingest`) to confirm or reject each hypothesis (typically 2-6 logs total). Log entry/exit, key values at decision points, which branch was taken, and important return values. Don't log every line, redundant data, or things you already know are correct.

### 3. Gather Evidence

Run the code and examine the debug log. For each hypothesis, decide:

- **CONFIRMED** - The logs prove this is the issue
- **REJECTED** - The logs prove this is NOT the issue
- **INCONCLUSIVE** - Need different instrumentation to test this

Only fix issues when you have clear runtime evidence pointing to the cause. Don't guess.

### 4. Fix and Verify

Keep instrumentation in place after a fix, run a verification test, and only remove debug logs once the fix is confirmed. That avoids "fixed one thing, broke another."

### Example Usage

Instrumentation writes NDJSON (one JSON object per line) to `.cursor/debug-{sessionId}.log`. For Cursor debugger to show entries, each line must include: **id**, **timestamp**, **location**, **message**, **data** (object). Optional: **runId**, **hypothesisId**, **sessionId**. The `/debug/ingest` route adds `id` when missing and normalizes `data` to an object; when writing from the server you must include `id` yourself (e.g. id: `log_${Date.now()}_${Math.random().toString(36).slice(2,10)}`).

**Server (Node):** write with `fs.appendFileSync`. Path is `path.join(process.cwd(), '.cursor', 'debug-{sessionId}.log')` (or use the exact log path provided in debug sessions).

```ts
import fs from "node:fs";
import path from "node:path";

const DEBUG_LOG = path.join(process.cwd(), ".cursor", `debug-${process.env.DEBUG_SESSION_ID ?? "default"}.log`);

// #region agent log
fs.appendFileSync(
  DEBUG_LOG,
  JSON.stringify({
    id: `log_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`,
    timestamp: Date.now(),
    location: "app/CheckoutService.ts:89",
    message: "Checking authentication before payment",
    hypothesisId: "A",
    data: {
      userId: currentUser?.id,
      isAuthenticated: currentUser != null,
      token: authToken,
    },
  }) + "\n"
);
// #endregion
```

**Client (browser):** POST one payload per call to the ingest route. The route appends to the same `.cursor/debug-{sessionId}.log` file.

```ts
// #region agent log
fetch("/debug/ingest", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    location: "app/CheckoutWidget.tsx:89",
    message: "Checking authentication before payment",
    hypothesisId: "B",
    data: {
      userId: currentUser?.id,
      isAuthenticated: currentUser != null,
    },
    timestamp: Date.now(),
  }),
}).catch(() => {});
// #endregion

```

## Remix v2 Guidelines

For proper loaders/actions, return plain objects directly:

```ts
// ✅ Good - TypeScript will properly infer types
export async function loader({ request }: LoaderFunctionArgs) {
  return {
    data: "some json response"
  };
};
// Exceptions:
// - Use `redirect()` for navigation responses
// - Use `new Response()` only when you require a custom headers/status


// ❌ Bad - TypeScript inference breaks
export const loader = async ({ request }: LoaderFunctionArgs) => {
  return json({ data: "bad response" }); // or Response.json()
};
```

For proper Metas

```ts
export const meta: MetaFunction<typeof loader> = ({
  data, // Data from the loader
  location, // Location object
  params, // File name driven params: concerts.$city.$date.tsx
}) => {
  // ...
};
```

## Testing Guidelines

- Vitest tests should be written alongside new code, not after
- Test files should be co-located next to their source files
- Every public method/function should have test coverage
- Test each code branch of success and error cases for good coverage
- For tests not deeply related to external APIs, you can mock them. But some tests may require external API testing to ensure conformance to new changes

### Specific Test

**Command:** `yarn test  path/to/file.test.ts  -t "should trigger foobar"`

It's cheaper on time and API costs to run a specific test you are focused on.

### Linting and Testing After Changes

**Lint:** `yarn lint`

Before you turn in your final response, you must lint.

**Test:** `yarn test:changed`

Before you turn in your final response, you should test, if it won't incur costs.
If the test is against real external API keys, ask the user first if we should test.

## GitHub Workflow Tips

If you need to check a Github workflow runner job's log, you can use the `gh` CLI:

- Ask for one of either:
  - URL. Route must contain: `*/actions/runs/*`
  - Run ID or Job ID.
- View it with:
  - `gh run view $RUN_ID --log`
  - `gh run view --log-failed --job=$JOB_ID`
