# AI Process Cursor Rules Guide

These Cursor rules are a great effort multiplier. Always remember to question and critically analyze all outputs.

# Setup

Copy to your project:

```
mkdir -p YOUR_PROJECT_PATH/.cursor/rules
cp ai_process_01_create_specification.mdc \
	ai_process_02_create_plan.mdc \
	ai_process_03_execute_plan.mdc \
	ai_process_04_create_release.mdc \
  YOUR_PROJECT_PATH/.cursor/rules
```

Then restart/start Cursor.

# Usage

## Create a specification 
**Rule**: `ai_process_01_create_specification.mdc`

The specification rule helps you quickly research and create an overall specification document that details the problem, approach, rationale, and technical details of a non-trivial task.

**Model Selection**: Always use thinking models like Gemini or Claude. Max is recommended, but gets expensive. Gemini is often better with overall architecture and research, but Claude has better understanding of mid to low level development concerns.

1. Open a chat window with no files in context.
2. Start with the prompt:
	`Reference the specification rule. Think very deeply.`
3. Converse, reference online resources, drop in screenshots or paste information.	 Talk about what you want to create, and think critically about suggestions. Talk about schemas and data structures, and their flows.
4. Save the specification, review carefully, and make adjustments.
5. Refine the specification further using:

   	```
	Refinement Task:
	1. Sanity check and critically analyze this specification document.
	1a. Think systematically and work step by step to allow you to make tool calls, read files, and solicit more information from me
	1b. While executing the analysis, if you encounter meaningful uncertainties or ambiguities, stop and ask clarifying quesitons.
	3. Suggest changes to the specification.
	4. Apply the changes after my approval.
	```
	
6. Call it done when you can *own* it.




## Create a Plan
**Rule**: `ai_process_02_create_plan.mdc `

**Model Selection**: Always use thinking models like Gemini or Claude. Max is recommended, but gets expensive. Gemini is often better with overall architecture and research, but Claude has better understanding of mid to low level development concerns.

1. Open a chat window with the specification document open and in context.

(TODO)

## Execute your Plan
**Rule**: `ai_process_03_execute_plan.mdc `

**Model Selection**: `claude-4-sonnet` (thinking) is best for Ruby/Javascript/Python.

1. Open a chat window with the plan document loaded in context.
2. Start with the prompt:
	`Reference the plan execution rule. Follow it strictly. Work step by step, thinking very deeply.`
3. The initial implementation plan is crucial. It's a good idea to follow up the initial proposal with prompts like:

	```
	Refinement Task:
	1. Sanity check and critically analyze your implementation plan.
	1a. Think systematically and work step by step to allow you to make tool calls, read files, and solicit more information from me
	1b. While executing the analysis, if you encounter meaningful uncertainties or ambiguities, stop and ask clarifying quesitons.
	3. Present an improved task implementation plan for my approval.
	```
4. When you are happy with the task implementation plan, prompt to continue, using:
   `Approved. Work step by step and think very deeply.`
5. When you are done completing a task and want to move to the next, keep the chat window open, and prompt to continue, using:
   `Refresh your memory of the plan execution rule and continue with the protocol.`