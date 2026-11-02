---
name: skill-router
description: 'Route a user instruction to the right installed skill before doing the work. Use at the start of any non-trivial task — especially when the request asks for a specialized deliverable (slides or PPT, spreadsheets, PDFs or Word docs, images or video, browser automation, research reports, code review, debugging, tests, deployment) or when several skills could plausibly apply and you must choose one. Also use when the user asks "which skill should handle this", "调用合适的 skill", "该用哪个技能", "自动匹配技能", or when one task spans several skills and needs sequencing. Skip for greetings, small talk, single-fact questions, and one-step edits where no skill adds value.'
license: MIT
---

# Skill Router

Turn an instruction into the skill that should handle it, then hand off and get out of the way.

## Why this exists

Skill descriptions are compressed into a catalog that competes for attention. Two failure modes follow:

- **Undertriggering** — the agent grinds out a spreadsheet by hand when a skill already encodes the right library, layout, and validation rules.
- **Pile-up** — the agent loads three overlapping skills, or picks the most keyword-similar one instead of the one that matches the actual deliverable.

This skill is a decision procedure for both. It is not a search engine and it does not know anything the catalog doesn't; its value is that it forces the routing question to be asked *once, explicitly* before work starts.

## The loop

### 0. Take the fast path when routing adds nothing

Answer directly, without routing, when:

- the user greets you, thanks you, or asks a single factual question
- the request is one shell command, one file read, or a small localized edit
- the user already named a skill (`/pdf`, "use the ppt-master skill", "按 diagnosing-bugs 来") — invoke that one, no deliberation
- the user says "just answer", "别用技能", "直接做"

Routing is a means, not a ritual. Running a taxonomy over "what's 2+2" is a tax on the user's time.

### 1. Write the task signature before looking at any skill

Fill five slots from the request. This is the step that prevents keyword matching from masquerading as understanding.

| Slot | Question | Example |
|---|---|---|
| **Action** | What is being done? | analyze, generate, convert, debug, review, deploy |
| **Object** | What is it being done to? | sales.xlsx, a PR, a failing test, a URL |
| **Deliverable** | What comes out? | .pptx, a patched repo, a report, a running service |
| **Domain** | What field or toolchain? | finance, React, Kubernetes, short-form video |
| **Shape** | One-shot or multi-step workflow? | "make a deck" is a workflow; "read this cell" is one-shot |

If a slot is genuinely unknown and changes which skill fits, that is the one question worth asking — ask it now, not after starting.

### 2. Build the candidate list

**Prefer the catalog already in your context.** If the runtime lists skills with their descriptions, that list is authoritative. Read it; don't rescan the disk.

Reach for the scanner only when:

- no catalog is visible in context
- the catalog looks stale or partial (a skill the user mentions is missing)
- you need a skill's filesystem path

```bash
python scripts/scan_skills.py --query "<the task signature, in one line>"
```

The script (next to this file) walks the standard skill roots, parses frontmatter, dedupes by name, and emits JSON: `{"skills": [{name, description, path, root}], "warnings": [...]}`. Add `--path DIR` for non-standard locations and `--format table` for human reading. Its `score` is a crude token-overlap hint — useful for ordering, never for deciding.

### 3. Score the candidates against the signature

Think in terms of "would following this skill produce a materially better result than doing it from memory?" The weights below anchor that judgment; they are not a formula to compute mechanically.

| Signal | Weight | Example |
|---|---|---|
| Skill named or aliased explicitly | 100 | "use pdf-master" |
| Deliverable matches what the skill produces | +30 | asks for `.pptx`; skill builds decks |
| Object and domain match the description | +25 | "Instagram reel", "Kubernetes manifest" |
| Action matches the skill's core verb | +20 | "diagnose" → a debugging skill |
| Description contains the user's trigger phrasing | +15 | "outlier videos", "brand tokens" |
| Workflow shape matches (multi-step vs one-shot) | +10 | "build me a deck" vs "read this cell" |
| Clear conflict with the skill's purpose | −40 | skill audits security; task is copywriting |

Decision rule: **route when the best candidate is clearly the intended workflow and no other skill is close.** As a rough bar, ≥55 with a lead of ≥15 over the runner-up. Below 35, no skill applies — proceed normally. The numbers are there to break ties and to stop you from talking yourself into a weak match.

Tie-breaks, in order:

1. **Specific beats general** — a skill about diagnosing build failures beats a general "research" skill for a flaky test.
2. **Workflow beats capability** — when the user wants a finished artifact, prefer the skill that owns the end-to-end pipeline over one that only covers a step.
3. **Still tied within ~10 points** — ask one compact question with the two or three real options. Do not silently pick and do not ask an open-ended "what do you want?".
4. **A skill already ran this turn** — don't re-route unless the task materially changed. Re-routing mid-task thrashes.

### 4. Invoke, then follow the skill

Invoke with the **exact name** from the catalog, through the runtime's skill mechanism (`Skill` tool in Claude Code / Cherry Studio). Do not reconstruct a skill from its description: the description is a signpost, the body is the instructions.

If the runtime has no skill tool, read `<skill-dir>/SKILL.md` and follow it directly. That is a legitimate equivalent — one extra file read, same instructions.

If invocation fails because the skill is missing or disabled, say so in one line and continue with your general capability. Don't fake the skill's workflow from memory.

### 5. Chain only when the task truly spans skills

A chain is justified when the deliverable needs two distinct workflows, e.g. research → deck, or implement → review. When chaining:

- cap it at two skills
- announce the sequence in one line before starting
- run them in order, passing the first skill's output as the second's input

Three or more skills in a row usually means the task should be split, or that you are collecting skills instead of doing work.

### 6. When nothing fits

Say it plainly: no installed skill covers this. Then do the task with general capability. If the need is specialized and likely recurring, *offer* to search for a skill (the `find-skills` skill or the marketplace) — but ask before installing anything.

## Reporting

One short line before the work, then stop narrating:

```
→ ppt-master (deck requested, .pptx deliverable)
```

Skip the line entirely on the fast path. The user wants the result, not the taxonomy.

## Anti-patterns

| Don't | Why |
|---|---|
| Route to `skill-router` itself | Infinite regress; this skill is the map, not a destination |
| Match on one generic word ("data", "file", "help") | Every skill's description contains those; the match is noise |
| Invoke a skill whose description merely *mentions* the topic | Mentioning ≠ owning the workflow |
| Load several similar skills "just in case" | Conflicting instructions produce worse output than one skill followed well |
| Ask the user to choose when one option is obviously right | Wastes a turn; state the choice and proceed |
| Re-route after work has started | Thrash; finish the current skill first |
| Trust the scanner's `score` as the decision | It is lexical overlap, not meaning |

## Examples

**1. Specialized deliverable → route**
> 把这个季度的销售数据做成一份汇报 PPT

Signature: generate / quarterly sales / .pptx / business reporting / workflow.
Route: `ppt-master`. It owns deck generation end to end; no other candidate is close.

**2. Format-scoped operation → route**
> 这个 xlsx 我只想保留第 3 个工作表，另存成一个新文件

Signature: extract-and-save / .xlsx / office documents / one-shot.
Route: `office-transform`. It is precisely "extract or edit a selection from xlsx/docx/pdf/pptx into a new file".

**3. Multi-step diagnostic → route**
> CI 上 test_checkout 偶尔失败，本地复现不了，帮我查查为什么

Signature: diagnose / flaky test / CI / debugging / open-ended loop.
Route: `diagnosing-bugs`. It is a feedback-loop discipline, not a one-shot answer.

**4. Review-shaped task → route**
> 看看这个 PR 的改动符不符合我们的规范

Signature: review / pull request / repo conventions / multi-step.
Route: `code-review`. Note the near-miss: a general "research" skill also reads code, but doesn't own review.

**5. Trivial request → no route**
> 写个 fibonacci 函数

One-step edit, no specialized workflow, no artifact. Answer directly. Routing here would be pure overhead.

**6. Genuine ambiguity → ask once**
> 帮我处理一下这个视频

Signature: process / video / ambiguous deliverable (analyze? transcribe? cut?).
Two plausible skills, neither clearly ahead. Ask: "要分析内容、生成字幕，还是剪辑？" then route. One question, not an interrogation.

More worked examples and the full rubric: `references/routing-rubric.md`.
