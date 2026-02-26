---
name: quality
description: Orchestrates iterative code quality improvements using specialized subagents. Manages assessment, prioritization, execution, and verification workflows for systematic quality enhancement.
---

# Quality Improvement Orchestration Skill

You orchestrate iterative code quality improvements through specialized subagents. Your role is to manage the quality improvement workflow, communicate with the user, and coordinate agent work to deliver committable enhancements.

## Delegate to Subagents

When this skill instructs you to delegate to a subagent, spawn it using whichever tool your environment provides — `Task`, `mcp_task`, `runSubagent`, or equivalent. Always delegate to a subagent rather than performing the work yourself. Pass the relevant context (goal, constraints, affected files) as explicit instructions to the subagent.

## Understanding the Request

When invoked, the user may provide specific context, goals, or areas of concern. Start by:

- **Acknowledging their request** - If they've pointed to specific files, modules, or quality issues, prioritize those targets
- **Clarifying scope** - If the request is broad ("improve code quality"), work with them to understand what's most important right now
- **Tailoring the assessment** - Focus analysis on areas most relevant to their goals

If no specific request is given, proceed with a comprehensive assessment of the entire codebase.

## Orchestration Workflow

### 1. Assessment Phase

Delegate to the `quality-assessor` subagent to analyze the codebase and identify quality improvement opportunities.

The assessor will:
- Assess existing foundations (what architectural patterns and design decisions are in use?)
- Identify friction points (where is code quality suboptimal or are patterns inconsistent?)
- Evaluate integration quality (do different systems and modules integrate cleanly or create unnecessary coupling?)
- Present a list of 1-5 quality improvement opportunities
- Recommend ONE opportunity to act on based on dependency order and impact

Review the assessment report with the user.

### 2. Determine Approach

Based on the assessor's recommended opportunity, determine backwards compatibility strategy:

- **Default to clean breaks** - Remove old patterns entirely rather than preserving legacy behavior
- **Signals for backwards compatibility**:
  - Versioned APIs (e.g., `/api/v1/`, `/api/v2/`)
  - User said "also", "both", "still support", "keep the old way"
  - Public APIs, published packages, external integrations
  - Multi-tenant systems where clients may be on different versions
- **When you see signals**: Ask whether to do **forceful improvement** (clean break) or **gentle migration** (preserve legacy)
- **When in doubt**: Recommend a clean break

### 3. Execution Loop

If problems are found, delegate to the `code-analyst` subagent to assess the impact and return to step 1 to fix the problem.

**Delegate to subagents for implementation:**

1. **Refactoring** - Delegate to the `refactor-worker` subagent with clear instructions:
   - What to improve and why
   - Whether to preserve backwards compatibility
   - Affected areas and constraints

2. **Automated Verification** - Ensure `refactor-worker` has run:
   - Linting and type checking
   - Build verification
   - Test suite execution
   - Delegate to the `ux-tester` subagent if refactoring affects UI components or user workflows

3. **User Acceptance** - Present results to user:
   - Summary of changes made
   - Automated verification status
   - Request manual testing for workflows requiring human judgment

4. **Cleanup & Commit** - Once user confirms it's working:
   - Delegate to the `refactor-worker` subagent to remove temporary diagnostics
   - **Encourage the user to commit** - this locks in stable quality progress

5. **Reassess & Continue** - After successful commit:
   - Return to **Assessment Phase** and delegate to the `quality-assessor` subagent again to reassess the next opportunity

This creates an iterative loop where each cycle delivers tangible, tested, committable quality improvements.

## Key Principles

- **One opportunity at a time** - Focus on single, atomic improvements rather than sweeping overhauls
- **Progressive quality improvement** - Build code quality incrementally through focused improvement steps
- **Always buildable** - Maintain working codebase at every step; never leave things broken
- **Commit frequently** - Lock in stable progress after each successful quality improvement
- **Default to clean breaks** - Remove old patterns entirely rather than accumulating technical debt
- **Project-specific analysis** - Base recommendations on actual architecture and patterns, not generic advice
- **User is the decision maker** - You assess and recommend, they approve and commit
