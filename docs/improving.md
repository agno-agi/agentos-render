# Turn operating evidence into improvements

Start on demand with a developer and the existing
[eval-and-improve skill](../.agents/skills/eval-and-improve/SKILL.md).
No continuously running improvement service is required.

1. **Choose a concrete outcome.** Select an agent or shared platform capability
   and define what better means. Use conversations, traces, tool results and
   evaluation records you are authorized to inspect. Sanitize examples before
   retaining them in a repository or shared Company Task.
2. **Diagnose before changing.** Reproduce the failure. Separate stale knowledge,
   instructions, tool selection, framework bugs, credentials and service failures.
   A dependency timeout is not evidence that the prompt needs strengthening.
3. **Keep a baseline.** Record the component/source version, model settings,
   cases and criteria. Save results and run/eval identifiers where available.
4. **Try a bounded candidate.** Change the responsible knowledge, instructions,
   integration, code or workflow. Run the same cases with fresh histories, plus
   relevant regressions and new variations. Inspect actual tool results and
   persisted effects, not just a successful HTTP response or fluent answer.
5. **Return something reviewable.** Keep the change, rationale, before/after
   evidence and useful regression cases together. Link the exact commit or
   published component version. Keep failed candidates too; do not weaken tests
   to manufacture improvement. A later revision needs fresh verification.
6. **Decide and retain.** Human review accepts or rejects the result. Adopted
   changes should survive as corrected knowledge, versioned instructions,
   committed code, workflows or regression cases. Do not leave the only record
   in temporary files or an engineer conversation.

Company can organize this work into Products, Projects and Tasks. The included
maintenance Routine proposes bounded improvements; inspect its saved schedule
and run history before relying on it. It does not automatically accept, execute,
merge or deploy proposals. Broader scheduled campaigns need explicit scope and
permissions; they are not enabled by this guide.

For delegated engineering, configure a [sandbox](sandboxes.md) and its repository.
Use selected fixtures and a test database, not production write credentials.
A fixture user alone does not isolate global tools. Give repository write access
explicitly when publishing is authorized, and verify the returned PR's repository,
branch and head before attaching it as a Task result. Do not forward the entire
API environment or checkpoint-store credentials into candidate code.

Framework-owned defects belong in Agno; keep the template thin. Preserve a
reproducer, test the fix at an exact Agno revision, update requirements and
rebuild both API and sandbox images. Report what was actually tested, including
uncertain results and untested deployment paths.
