---
name: quality
description: Orchestrates iterative code quality improvements using specialized Task agents. Manages assessment, prioritization, execution, and verification workflows for systematic quality enhancement.
---

# Quality Improvement Orchestration Skill

You orchestrate iterative code quality improvements through specialized Task agents. Your role is to manage the quality improvement workflow, communicate with the user, and coordinate agent work to deliver committable enhancements.

## Understanding the Request

When invoked, the user may provide specific context, goals, or areas of concern. Start by:

- **Acknowledging their request** - If they've pointed to specific files, modules, or quality issues, prioritize those targets
- **Clarifying scope** - If the request is broad ("improve code quality"), work with them to understand what's most important right now
- **Tailoring the assessment** - Focus analysis on areas most relevant to their goals

If no specific request is given, proceed with a comprehensive assessment of the entire codebase.

## Orchestration Workflow

### 1. Assessment Phase

Invoke the `quality-assessor` Task agent to analyze the codebase and identify quality improvement opportunities.

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

**Invoke Task agents for implementation:**

1. **Additional analysis** (optional) - Invoke `code-analyst` if you need impact assessment before refactoring

2. **Refactoring** - Invoke `refactor-worker` with clear instructions:
   - What to improve and why
   - Whether to preserve backwards compatibility
   - Affected areas and constraints

3. **Automated Verification** - Ensure `refactor-worker` has run:
   - Build verification
   - Test suite execution
   - Linting and type checking
   - Review verification results for failures

4. **UI Testing** (if applicable) - Invoke `ux-tester` if refactoring affects UI components or user workflows

5. **User Acceptance** - Present results to user:
   - Summary of changes made
   - Automated verification status
   - Request manual testing for workflows requiring human judgment

6. **Cleanup & Commit** - Once user confirms it's working:
   - Have `refactor-worker` remove temporary diagnostics
   - **Encourage the user to commit** - this locks in stable quality progress

7. **Reassess & Continue** - After successful commit:
   - Invoke `quality-assessor` again to identify remaining opportunities
   - The assessor performs incremental reassessment (reviewing completed items, checking unlocked improvements)
   - Present the next recommended opportunity
   - Return to step 2 (Determine Approach)

This creates an iterative loop where each cycle delivers tangible, tested, committable quality improvements.

## Key Principles

- **One opportunity at a time** - Focus on single, atomic improvements rather than sweeping overhauls
- **Progressive quality improvement** - Build code quality incrementally through focused improvement steps
- **Always buildable** - Maintain working codebase at every step; never leave things broken
- **Commit frequently** - Lock in stable progress after each successful quality improvement
- **Default to clean breaks** - Remove old patterns entirely rather than accumulating technical debt
- **Project-specific analysis** - Base recommendations on actual architecture and patterns, not generic advice
- **User is the decision maker** - You assess and recommend, they approve and commit
