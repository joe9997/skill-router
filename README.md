# skill-router

让 agent 在动手之前，先把你的指令路由到**正确的已安装 skill**，而不是凭关键词碰运气。

![License](https://img.shields.io/badge/license-MIT-blue)
![Agent Skills](https://img.shields.io/badge/format-Agent%20Skills-6b46c1)
![Python](https://img.shields.io/badge/python-3.9%2B-3776ab)

---

## 它解决什么问题

一个装了 40 个 skill 的 agent，真正会用的往往只有最常被提到的那 5 个。剩下 35 个的 `description` 挤在上下文里，谁也没被认真读过。结果就是两种失败：

| 失败模式 | 表现 | 代价 |
|---|---|---|
| **漏用** | 明明有 `ppt-master`，agent 还是一行行手搓 PPT | 每次都在重新发明轮子，质量还不稳定 |
| **乱用** | 关键词对上哪个就用哪个，或者一次加载三个重叠的 skill | 指令互相冲突，输出比不用还差 |

`skill-router` 是一套**显式的路由决策流程**：先写任务签名，再对照 skill 目录打分，选一个，然后闭嘴干活。

它不是搜索引擎，也不比运行时多知道什么。它的价值在于把"该用哪个 skill"这个问题**强制问一次**，并且给出可解释的选择理由。

## 它怎么工作

```text
用户指令
   │
   ├─ 打招呼 / 一步能搞定 / 用户点名了 skill / 说了"别用技能"
   │        └──────────────────────────────────► 直接回答，不路由
   ▼
1. 写任务签名：动作 · 对象 · 交付物 · 领域 · 形态（一次性 vs 多步骤）
   ▼
2. 取候选：上下文里的 skill 目录优先；没有才跑 scripts/scan_skills.py
   ▼
3. 打分：交付物匹配 > 对象匹配 > 动作匹配；明确点名直接 100 分
   ▼
4. 决策：最高分 ≥55 且领先 ≥15 → 调用
   │        两个候选差 10 分内 → 问一个二选一问题
   │        最高分 <35 → 没有合适 skill，正常做
   ▼
5. 用精确名字调用 Skill → 按 skill 的正文执行
   ▼
一行说明：→ ppt-master (deck requested, .pptx deliverable)
```

关键设计：

- **交付物优先于关键词**。用户要的是 `.pptx`，就找产出 `.pptx` 的 skill，而不是描述里出现"PPT"三个字的 skill。
- **具体压过通用**。"诊断 CI 上的偶发失败"应该走 `diagnosing-bugs`，不是泛泛的 `research`。
- **最多串两个 skill**。三个以上通常意味着任务该拆了，或者你在收集 skill 而不是在干活。
- **不在简单任务上表演流程**。"写个 fibonacci" 不需要路由。
- **绝不路由到自己**。

## 安装

skill 的本质是一个包含 `SKILL.md` 的文件夹，放到运行时的 skills 目录即可。

### Cherry Studio

```bash
git clone https://github.com/<your-name>/skill-router.git
cp -r skill-router "$CHERRY_STUDIO_SKILLS_DIR/skill-router"
```

Windows PowerShell：

```powershell
git clone https://github.com/<your-name>/skill-router.git
Copy-Item -Recurse .\skill-router "$env:APPDATA\CherryStudio\Data\Skills\skill-router"
```

### Claude Code

用户级（所有项目可用）：

```bash
git clone https://github.com/<your-name>/skill-router.git
cp -r skill-router ~/.claude/skills/skill-router
```

或项目级：复制到 `<repo>/.claude/skills/skill-router/`。

### 其他 runtime

任何支持 Agent Skills 格式（`SKILL.md` + YAML frontmatter）的 runtime 都能用。如果它没有 `Skill` 工具，skill 里写了降级路径：直接读 `<skill-dir>/SKILL.md` 并照做。

## 使用

装好之后不需要特别操作。它会按 `description` 里的触发条件在任务开始时自动介入：

> **你**：把这个季度的销售数据做成一份汇报 PPT
>
> **Agent**：→ ppt-master (deck requested, .pptx deliverable)
> 然后开始做 PPT。

也可以手动点名：

```
/skill-router
用 skill-router 看看这活该走哪个技能
```

### 什么时候它不该触发

- "你好"、"谢谢"、单一事实问答
- 一条命令、读一个文件、几行小改动
- 你已经点名了 skill（`/pdf`、"用 ppt-master"）
- 你明确说了"直接做，别用技能"

这些都写在 skill 的 fast path 里，路由不会在它们身上浪费一轮。

## 扫描器

`scripts/scan_skills.py` 是一个纯标准库的小工具，用来在运行时**没有**把 skill 目录放进上下文时，自己扫出一份 catalog。它也会做结构校验。

```bash
# 扫描标准位置，输出 JSON
python scripts/scan_skills.py

# 按相关性排序，人读格式
python scripts/scan_skills.py --query "把销售数据做成 PPT" --format table

# 只扫指定目录（测试/CI 用）
python scripts/scan_skills.py --path ./my-skills --no-defaults

# 有结构问题就以非零退出（可接进 CI）
python scripts/scan_skills.py --strict
```

输出：

```json
{
  "roots": ["C:\\Users\\you\\AppData\\Roaming\\CherryStudio\\Data\\Skills"],
  "skills": [
    {
      "name": "ppt-master",
      "description": "AI-driven presentation workflow for generating editable PPTX decks...",
      "path": "...\\ppt-master\\SKILL.md",
      "root": "...\\Data\\Skills",
      "modified": 1760000000,
      "score": 14
    }
  ],
  "warnings": ["missing description: ...\\broken-skill\\SKILL.md"]
}
```

标准扫描位置（按优先级，同名取先出现的）：

1. `--path` 指定的目录
2. `$CHERRY_STUDIO_SKILLS_DIR`
3. `$CLAUDE_SKILLS_DIR`、`$AGENT_SKILLS_DIR`
4. `./.claude/skills`、`./skills`
5. `~/.claude/skills`、`~/.config/claude/skills`、`~/.agents/skills`

> `score` 只是词面重叠（含中文 bigram），用来排序，**不能当作路由结论**。语义匹配是模型的事。

校验规则：

- `name` 必须等于文件夹名
- `description` 必须存在（它是路由唯一能看到的东西）
- 同名 skill 只保留优先级最高的那个并给出 warning

## 仓库结构

```text
skill-router/
├── SKILL.md                    # 技能正文：路由流程、打分表、反模式、示例
├── references/
│   └── routing-rubric.md       # 完整评分细则、歧义处理、串行规则、目录维护
├── scripts/
│   └── scan_skills.py          # skill 目录扫描器 + 结构校验
├── tests/
│   └── test_scan_skills.py     # 15 个单元测试，零依赖
├── evals/
│   └── evals.json              # 12 条真实路由测试用例（含不该触发的）
├── .github/workflows/ci.yml    # Python 3.9–3.13 测试 + skill 结构校验
├── LICENSE
└── README.md
```

## 设计取舍（先说清楚）

**运行时本来就会选 skill。** Claude Code、Cherry Studio 等会把每个 skill 的 `name + description` 放进上下文，由模型自行判断是否调用。所以这个 skill 不是"给 agent 增加路由能力"，而是：

- 给选择过程一个**可复现的结构**，而不是每次凭感觉
- 在描述含糊、skill 数量多、多个候选接近时，给出**显式的取舍理由**
- 提供**扫描器**，覆盖运行时没有暴露 catalog 的情况
- 在路由失败时留下**可读的一行记录**，方便你事后调 description

它不会让 agent 变得无所不能，也不保证 100% 选对。它是 prompt 层的协议，不是代码层的路由器——如果你要的是确定性路由，应该写 harness，而不是写 skill。

**开销。** 它会给非平凡任务增加一次决策。fast path 已经排除了大部分简单请求，但如果你觉得它太吵，可以直接删掉 `SKILL.md` 里的 reporting 那一段，或者收窄 frontmatter 的 description。

**为什么不内置 skill 清单。** 清单会过时。路由必须读**当前**目录，所以 skill 正文只讲怎么取候选，不硬编码任何 skill 名字（示例除外）。

## 开发

```bash
python -m unittest discover -s tests -v
python scripts/scan_skills.py --strict
```

CI 会在 Python 3.9 / 3.11 / 3.13 上跑这两条。没有任何第三方依赖，不需要 `pip install`。

欢迎 PR。如果改了路由规则，请同步更新 `references/routing-rubric.md` 和 `evals/evals.json`。

## English quickstart

`skill-router` is a meta-skill that routes a user instruction to the right installed skill. It extracts a task signature (action, object, deliverable, domain, shape), scores candidates from the live skill catalog, invokes one by exact name, and reports the choice in a single line.

It is not magic: runtimes already expose skill descriptions to the model. This skill adds an explicit, repeatable decision procedure, a scanner for runtimes that don't, and a short audit trail.

```bash
git clone https://github.com/<your-name>/skill-router.git
cp -r skill-router ~/.claude/skills/skill-router   # or your runtime's skills dir
```

## License

MIT. See [LICENSE](LICENSE).
