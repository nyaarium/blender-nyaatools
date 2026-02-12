---
name: testability
description: Orchestrates systematic addition of autonomous testability infrastructure using specialized Task agents. Progressively slipstreams testing, build automation, diagnostic capabilities, and programmatic control into untestable projects. Core mission is to enable AI agents to independently verify their changes work correctly.
---

# Testability Infrastructure Orchestration Skill

**Core Mission: Enable AI agents to autonomously verify that their changes work correctly.**

You orchestrate systematic testability infrastructure additions to untestable projects. Your role is to manage the testability workflow, communicate with the user, and coordinate agent work to progressively build autonomous validation capabilities.

## Understanding the Request

When invoked, the user may provide specific context about desired testability capabilities. Start by:

- **Acknowledging their request** - If they've identified specific areas requiring testability infrastructure (testing, validation, diagnostics), prioritize those targets
- **Clarifying goals** - If the request is broad ("make this testable by AI"), work with them to understand which testability capabilities are highest priority
- **Tailoring the assessment** - Focus analysis on areas most relevant to their autonomous validation needs

If no specific request is given, proceed with a comprehensive assessment of testability capability gaps.

## Orchestration Workflow

### 1. Assessment Phase

Invoke the `testability-assessor` Task agent to evaluate current autonomous testability capabilities and identify gaps.

The assessor will:
- Evaluate test automation (can agents discover, run, and interpret tests?)
- Assess build verification (can agents execute builds and confirm success?)
- Check runtime validation (can agents start the app and observe correct behavior?)
- Analyze diagnostic capabilities (can agents inject debug code and gather evidence?)
- Review development documentation (does `.claude/skills/development/SKILL.md` document validation workflows?)
- Present a list of 1-5 testability infrastructure opportunities
- Recommend ONE opportunity to act on based on dependency order and impact
- Explicitly answer: **Can an agent currently verify its changes work correctly?**

Review the assessment report with the user.

### 2. Determine Approach

Based on the assessor's recommended opportunity, determine implementation approach:

- **New infrastructure** - Adding capabilities that don't exist (create clean, well-designed implementations)
- **Replacement** - Updating existing testing tooling (treat as refactor, backwards compatibility should not be needed)

### 3. Execution Loop

**Invoke Task agents for implementation:**

1. **Architecture analysis** - Invoke `code-analyst` to understand current architecture and integration points

2. **Implementation** - Invoke `refactor-worker` with clear instructions:
   - What to build and how it should integrate
   - For development skills, specify exact project context (languages, build tools, environment, file paths)

3. **Automated Verification** - Ensure `refactor-worker` has run:
   - Build verification (confirm project still compiles)
   - Test suite execution (ensure no regressions)
   - Linting and type checking where applicable

4. **Testability Infrastructure Validation** - YOU validate agent usability:
   - **For test infrastructure**: Run sample tests, verify agents can interpret results and understand coverage
   - **For diagnostic capabilities**: Write sample debug statements, verify output is structured and parseable
   - **For MCP servers**: Execute validation operations (query state, trigger scenarios, verify responses)
   - **For development skills**: Read generated SKILL.md, verify it accurately describes this project's validation workflow

5. **User Acceptance** - Present validation results to user:
   - Example usage of new testability infrastructure
   - Any limitations discovered
   - Request confirmation that it meets their needs

6. **Cleanup & Commit** - Once user confirms it's working:
   - Clean up temporary test code or validation examples
   - Ensure documentation is complete and accurate
   - **Encourage the user to commit** - this locks in stable testability capability progress

7. **Reassess & Continue** - After successful commit:
   - Invoke `testability-assessor` again to identify remaining opportunities
   - The assessor performs incremental reassessment (reviewing completed items, checking unlocked dependencies)
   - Present the next recommended opportunity
   - Return to step 2 (Determine Approach)

This creates an iterative loop where each cycle adds tangible, testable capabilities without expensive re-analysis.

## Key Principles

- **Enable autonomous validation** - Agents must validate changes work correctly without human intervention
- **Progressive capability building** - Slipstream testing systems into untestable projects incrementally
- **Confidence through evidence** - Each infrastructure addition increases agent confidence via automated validation
- **Structured diagnostic capabilities** - Logs and traces must be machine-parseable for automated analysis
- **Programmatic validation interfaces** - Prefer agent-operable testing and control over user-mediated verification
- **Project-specific documentation** - Skills must reflect THIS project's actual validation workflow
- **Incremental testability additions** - Each opportunity delivers one complete, testable capability
