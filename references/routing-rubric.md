# Routing rubric

Reference material for `skill-router`. Read this when a routing decision is genuinely close, or when you are tuning the skill.

## Contents

1. [What "matching" means](#what-matching-means)
2. [Full scoring table](#full-scoring-table)
3. [Worked examples](#worked-examples)
4. [Ambiguity policy](#ambiguity-policy)
5. [Chains](#chains)
6. [Catalog hygiene](#catalog-hygiene)

## What matching means

A skill is a bundle of *procedural knowledge*: commands that work, formats that don't break, orderings that avoid rework. Routing is justified when that knowledge is worth more than the cost of loading it.

So the question is never "does this description contain words from the request?" It is:

> If I follow this skill, will the result be materially better than what I would produce from general capability?

A skill that merely *mentions* the user's topic fails this test. A skill that *owns the workflow* passes it.

Two corollaries:

- A vague skill with a broad description is not a strong match just because it is broad. Broad descriptions match everything, which means they discriminate nothing.
- A narrowly-scoped skill that exactly fits the deliverable beats a well-known general skill every time.

## Full scoring table

Scores are additive. Treat the total as evidence, not a verdict.

### Positive signals

| Signal | Weight | Notes |
|---|---|---|
| User names the skill, or a known alias | 100 | Immediate route. Do not deliberate. |
| Deliverable matches the skill's output | +30 | The strongest semantic signal: `.pptx`, a signed commit, a patched branch |
| Object matches | +25 | The noun the skill operates on: "Instagram reel", "Kubernetes manifest", "xlsx" |
| Action matches the skill's core verb | +20 | "diagnose", "review", "convert", "scaffold" |
| Skill's trigger phrases appear in the request | +15 | Trigger phrases are curated for exactly this |
| Workflow shape matches | +10 | A skill that owns a multi-step pipeline matches a request for a finished artifact |
| Skill covers a step the user explicitly wants | +10 | "research first, then build" → a research skill is a legitimate first hop |

### Negative signals

| Signal | Weight | Notes |
|---|---|---|
| Skill's purpose conflicts with the request | −40 | Security audit skill, but the task is copywriting |
| Skill is deprecated / superseded | −40 | Prefer the successor; mention the substitution |
| Skill requires an unavailable dependency | −25 | It will fail mid-run; better to say so up front |
| Skill is the router itself | −∞ | Never route to `skill-router` |

### Thresholds

| Total | Action |
|---|---|
| ≥ 55 with a ≥ 15 lead | Route |
| 40–54, or a lead < 15 | Close call — see ambiguity policy |
| 35–39 | Mention the possibility in one line, then proceed generally |
| < 35 | No skill applies; do the task directly |

## Worked examples

### A. Obvious route

**Request:** "帮我把这份 PDF 合同里的签字页提取出来，存成单独的 PDF"

| Candidate | Score | Reasoning |
|---|---|---|
| `office-transform` | 30 + 25 + 20 = 75 | deliverable (new PDF) + object (PDF) + action (extract a selection) |
| `pdf` (generic) | 25 | object matches, but no selection workflow described |
| `research` | 0 | unrelated |

Route `office-transform`. Lead is decisive.

### B. Near-miss that a keyword matcher gets wrong

**Request:** "Read this article and tell me whether its benchmark numbers are trustworthy"

| Candidate | Score | Reasoning |
|---|---|---|
| `research` | 0 | It searches *for* sources; here the source is given |
| `diagnosing-bugs` | 0 | "trustworthy" is not a bug |
| No skill | — | This is analysis of a provided artifact |

The word "research" appears nowhere, and that is correct. The task is reading comprehension plus judgment, not source gathering. Proceed directly. This is the class of error keyword routing makes most often.

### C. Two skills, one deliverable

**Request:** "调研一下竞品的定价策略，然后做成一份给管理层的 PPT"

| Candidate | Score | Reasoning |
|---|---|---|
| `ppt-master` | 30 + 25 + 10 = 65 | .pptx deliverable, deck workflow |
| `research` | 20 + 10 = 30 | research action, but no artifact ownership |

This is a chain: `research` → `ppt-master`. The deck is the deliverable, so `ppt-master` is the anchor; research is a justified first hop because the user explicitly asked for it. Announce the sequence, run two skills, stop.

Do not run three. If a third looks necessary, split the task with the user instead.

### D. Generic skill vs specific skill

**Request:** "我们的 React 组件测试里全是 `as` 类型断言，想换掉"

| Candidate | Score | Reasoning |
|---|---|---|
| `migrate-to-shoehorn` | 100 | The request describes exactly this migration |
| `tdd` | 20 | Tests are involved, but the task is migration, not test-first development |

Route the specific one. "Tests" as a keyword should not pull in a testing-discipline skill when a migration skill exists.

### E. Skill exists but is the wrong phase

**Request:** "这个功能还没写，帮我先想清楚接口再动手"

| Candidate | Score | Reasoning |
|---|---|---|
| `codebase-design` | 25 + 20 = 45 | Designing a module interface is exactly its subject |
| `tdd` | 10 | Building comes later; the user explicitly said "还没写" |

Close call at 45, but the request is unambiguous in intent: design before implementation. Route `codebase-design` and note that `tdd` is the natural next step. This is the "state the choice and proceed" case — don't ask.

### F. No skill, recurring need

**Request:** "把这段中文翻译成正式的商务英文"

No installed skill owns translation. Say so, do the translation well, and — only if the user signals this recurs — offer to find a skill. Do not install anything unprompted.

## Ambiguity policy

Ask a question only when **all three** hold:

1. two or more candidates score within ~10 points
2. they would produce materially different outputs
3. the request does not itself disambiguate

When asking:

- offer 2–3 concrete options, not an open question
- put the most likely option first
- one question, then act on the answer

```
这份视频你主要想要：
1. 内容分析（讲了什么、结构如何）
2. 字幕/转录
3. 剪辑成短视频
```

Do **not** ask when one candidate clearly leads — state the choice in the routing line and proceed. A question costs a turn; spending it on something you could have decided is worse than being occasionally wrong and correcting.

## Chains

A chain is two skills where each owns a distinct phase and the phases are explicit in the request.

| Pattern | Example | Why it works |
|---|---|---|
| Research → Produce | research → ppt-master | Evidence then artifact |
| Produce → Review | implement → code-review | Build then verify |
| Analyze → Fix | diagnosing-bugs → tdd | Find cause then lock it with a test |

Rules:

- maximum two
- announce the sequence before starting
- the second skill consumes the first's output explicitly
- if the first skill's output changes what the second should do, re-read the second's description before invoking — it may no longer fit

## Catalog hygiene

The router is only as good as the descriptions it reads. When you notice a catalog problem, say so; don't silently work around it.

| Problem | Symptom | Fix |
|---|---|---|
| Description is a feature list | Matches everything, discriminates nothing | Rewrite around *when* to use it and *what artifact* it produces |
| Duplicate names | Scanner dedupes; one skill is shadowed | Rename or remove the shadowed copy |
| `name` ≠ folder name | Scanner warns; some runtimes fail to load it | Align them |
| Missing description | Skill is invisible to routing | Add one — it is the only thing routing sees |
| Stale skill | Matches requests it can no longer fulfill | Update or delete |

Run `python scripts/scan_skills.py --strict` in CI to catch the structural issues (missing description, name mismatch, duplicates).
