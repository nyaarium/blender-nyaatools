// Debug Logger for AI Agent Instrumentation
// Writes NDJSON to .cursor/debug-{sessionId}.log for structured, machine-parseable output
// Adapt this template to your project's architecture and logging conventions

import fs from "node:fs";
import path from "node:path";

const LOG_DIRECTORY = path.join(process.cwd(), ".cursor");
const SESSION_ID = process.env.DEBUG_SESSION_ID ?? "default";
const LOG_FILE = path.join(LOG_DIRECTORY, `debug-${SESSION_ID}.log`);

let logCounter = 0;

/**
 * Log debug information for AI agent analysis.
 * Writes structured NDJSON entries that agents can programmatically parse.
 *
 * @param {string} location - Source location (e.g., "src/services/auth.js:142")
 * @param {string} message - Human-readable description of the observation
 * @param {Object} options - Optional configuration
 * @param {string} [options.hypothesisId] - Hypothesis identifier for A/B debugging (e.g., "A", "B")
 * @param {Object} [options.data] - Structured key-value data for analysis
 */
export function debugLog(location, message, options = {}) {
  const { hypothesisId = null, data = {} } = options;

  try {
    // Ensure log directory exists
    if (!fs.existsSync(LOG_DIRECTORY)) {
      fs.mkdirSync(LOG_DIRECTORY, { recursive: true });
    }

    // Build structured log entry
    const entry = {
      id: `log_${Date.now()}_${++logCounter}`,
      timestamp: Date.now(),
      location,
      message,
      data,
      ...(hypothesisId && { hypothesisId }),
    };

    // Append as single-line JSON (NDJSON format)
    fs.appendFileSync(LOG_FILE, JSON.stringify(entry) + "\n");
  } catch {
    // Silently fail - instrumentation must never break the application
  }
}

/**
 * Clear the debug log.
 * Call at the start of a debugging session or test run.
 */
export function clearDebugLog() {
  try {
    if (fs.existsSync(LOG_FILE)) {
      fs.unlinkSync(LOG_FILE);
    }
  } catch {
    // Silently fail
  }
}

/**
 * Read all log entries for AI agent analysis.
 * Returns parsed NDJSON entries as an array of objects.
 *
 * @returns {Array<Object>} Array of log entry objects
 */
export function readDebugLog() {
  const entries = [];

  try {
    if (!fs.existsSync(LOG_FILE)) {
      return entries;
    }

    const content = fs.readFileSync(LOG_FILE, "utf-8");
    for (const line of content.split("\n")) {
      if (!line.trim()) continue;
      entries.push(JSON.parse(line));
    }
  } catch {
    // Return partial results on parse errors
  }

  return entries;
}

/**
 * Filter log entries by hypothesis ID.
 * Useful for comparing behavior between code paths during debugging.
 *
 * @param {string} hypothesisId - The hypothesis to filter by (e.g., "A" or "B")
 * @returns {Array<Object>} Filtered log entries
 */
export function getEntriesByHypothesis(hypothesisId) {
  return readDebugLog().filter((entry) => entry.hypothesisId === hypothesisId);
}
