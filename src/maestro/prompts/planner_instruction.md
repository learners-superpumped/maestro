# Planning Request

Analyze the following goals and signals, then design an execution plan to achieve each goal.

## Goals

{goals}

{history_section}

## Signals

{signals}

## Planning Procedure

Think through these steps in order, then generate tasks based on your analysis.

### 1. Goal Analysis

- Define the concrete end-state for each goal
- Identify the gap between current state and target state

### 2. History Review (if history is provided)

- Completed tasks: identify what has already been achieved — do not duplicate
- Failed tasks: analyze root cause and use a different approach

### 3. Strategy Design

- Design the full path to goal achievement
- Place research/investigation tasks before execution tasks when uncertainty is high
- Ensure each step produces a verifiable intermediate result

### 4. Task Decomposition

- Create as many tasks as needed to fully achieve the goal (no limit on count)
- Each task must focus on one clear deliverable
- Write instructions detailed enough for an agent with zero context to execute

## Task Fields

Each task MUST include:

- agent — agent type to execute the task
- title — clearly express the outcome to be achieved
- instruction — MUST include: CONTEXT, OBJECTIVE, EXECUTION STEPS, CONSTRAINTS, COMPLETION CRITERIA
- priority — 1 (highest) to 5 (lowest)
- goal_id — related goal ID
- approval_level — 0 (auto) to 2 (manual approval required)
- success_criteria — how to judge if this task succeeded
- depends_on_steps — array indices (0-based) of prerequisite tasks. Leave empty for parallelizable tasks

## Example

[{{"title": "Research competitor pricing", "agent": "default", "instruction": "CONTEXT: We need to evaluate our product's price competitiveness against the market.\n\nOBJECTIVE: Produce a comparison report of pricing policies from 3 major competitors.\n\nEXECUTION STEPS:\n1. Collect current pricing from competitors A, B, C official websites\n2. Compare plan structures (free/paid/enterprise) across each\n3. Identify discount policies, annual billing benefits, and other terms\n4. Compile into a comparison table\n\nCONSTRAINTS: Use only publicly available pricing data.\n\nCOMPLETION CRITERIA: A comparison table covering all 3 competitors' pricing is ready.", "priority": 2, "goal_id": "goal-1", "success_criteria": "Competitor pricing comparison table complete"}},
{{"title": "Analyze internal cost structure", "agent": "default", "instruction": "CONTEXT: Before adjusting prices, we must understand our current cost structure.\n\nOBJECTIVE: Analyze per-product costs and margin rates.\n\nEXECUTION STEPS:\n1. Calculate direct costs per product (servers, licenses, etc.)\n2. Verify indirect cost allocation methodology\n3. Compute current margin rates\n4. Determine the feasible range for price adjustments\n\nCONSTRAINTS: Use latest quarterly financial data.\n\nCOMPLETION CRITERIA: Per-product cost/margin analysis table is complete.", "priority": 2, "goal_id": "goal-1", "success_criteria": "Per-product margin analysis complete"}},
{{"title": "Design new pricing model", "agent": "default", "instruction": "CONTEXT: Based on competitor analysis and cost analysis results, design a new pricing model.\n\nOBJECTIVE: Propose a pricing model that is competitive yet maintains profitability.\n\nEXECUTION STEPS:\n1. Review the competitor comparison table and cost analysis from predecessor tasks\n2. Design 3 pricing scenarios (conservative / neutral / aggressive)\n3. Run revenue projections for each scenario\n4. Select recommended scenario with supporting rationale\n\nCONSTRAINTS: Margin must not drop below 20%.\n\nCOMPLETION CRITERIA: Document with 3 scenarios and a recommended option is complete.", "priority": 1, "goal_id": "goal-1", "depends_on_steps": [0, 1], "success_criteria": "3 pricing scenarios with recommendation documented"}}]

Return as a JSON array.
