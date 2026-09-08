# 数学聊天与研究记录项目

这个项目用于在 Codex 桌面版里日常和 AI 聊数学、查资料、尝试证明，并把重要内容记录到本地 Markdown 文件中。每个数学问题使用一个独立的顶层目录；当前项目名称、角色和说明以 `projects.json` 为准。

此公开仓库只包含通用工具和虚构示例。真实问题的目录名、README、注册表标题与说明也属于私有研究信息；请在私有工作副本中维护，提交前运行公开范围检查。

## 快速开始

打开 Codex 桌面版后，可以直接发：

```text
继续 example_math_problem。先读 research_state.md 和 subgoal.md 的当前部分，核对目标和假设，再读最近 3–5 条进度、相关日期笔记及当前问题链接到的证据，按需检索历史记忆。总结当前状态，然后围绕我下面的问题推进：...

要求：
- 数学结论标注置信度；
- 每个证明尝试说明关键假设；
- 失败路径写入 memory/failed_paths.md；
- 有实质进展时更新今天的日期笔记；
- 结束时给出下一步建议。
```

创建自己的问题后，也可以直接发：

```text
继续 example_math_problem。先读取该目录的 research_state.md 和相关详细记录，再从 Current Goal 继续。
```

如果只想临时讨论，不想改文件：

```text
先别改文件，我们只讨论这个数学问题：...
```

`AGENTS.md` 是给 Codex 读取的行为指令；这份 README 是给人看的使用说明。

## 目录结构

```text
.
├── README.md
├── AGENTS.md
├── reference_index.py
├── search_references.py
├── search_arxiv_theorems.py
├── inbox/
├── skills/
├── templates/
│   ├── research_state.md
│   ├── pro_task.md
│   └── pro_review.md
└── example_math_problem/
```

每个问题目录内部使用相同结构：

```text
<problem_dir>/
    ├── research_state.md
    ├── goal.md
    ├── progress.md
    ├── subgoal.md
    ├── YYYY-MM-DD.md
    ├── notes/
    ├── memory/
    ├── refs/
    ├── downloads/
    └── handoff/
```

常用文件：

| 路径 | 用途 |
| --- | --- |
| `AGENTS.md` | 给 Codex 桌面版读取的 agent 行为指令 |
| `projects.json` | 问题目录、标题、角色和说明的唯一注册表 |
| `templates/research_state.md` | 新建问题目录时使用的统一状态模板 |
| `docs/reference_workflow.md` | PDF、TeX、TXT 后备、版本与校验信息的统一规范 |
| `inbox/` | 跨问题、尚未确定归属或尚未整理的外部材料入口 |
| `<problem_dir>/handoff/` | 该问题与网页端 Pro 的对话任务、最终交接稿和审核记录；除 `.gitkeep` 外均不提交 |
| `<problem_dir>/research_state.md` | 当前问题的六栏紧凑状态页 |
| `<problem_dir>/goal.md` | 当前数学问题的长期目标和精确陈述 |
| `<problem_dir>/progress.md` | 跨会话进展摘要 |
| `<problem_dir>/subgoal.md` | 当前证明分解和子目标 |
| `<problem_dir>/YYYY-MM-DD.md` | 每日研究笔记 |
| `<problem_dir>/memory/` | 推论、例子、反例、失败路径、搜索结果等结构化记忆 |
| `<problem_dir>/refs/` | PDF、论文笔记、提取文本和本地索引 |

## 状态页与详细记录

两套记录结合使用，但职责不同：`research_state.md` 是当前状态和导航入口，原有文件保存完整事实、推导与历史。

| 状态页栏目 | 状态页保留 | 详细记录位置 |
| --- | --- | --- |
| `Research State` | 当前状态、置信度、假设和简短摘要 | `goal.md`、`progress.md`、每日笔记 |
| `Known Theorems` | 当前最关键的定理 | `memory/immediate_conclusions.md`、来源笔记 |
| `Open Problems` | 主要未决问题 | `subgoal.md`、`memory/subgoals_state.md` |
| `Failed Attempts` | 路线和一句失败原因 | `memory/failed_paths.md` |
| `Current Goal` | 当前唯一目标、下一步和阻碍 | `goal.md`、`subgoal.md` |
| `References` | 当前最相关的文献 | `memory/search_results.md`、`refs/` |

数学结论、证据和历史以详细文件为准；当前工作快照以 `research_state.md` 为准。有实质进展时，先更新详细文件，再刷新状态页。状态页只写摘要并链接详情，不复制长证明和完整搜索记录。

状态页采用 250 行、24 KiB 的建议上限。**当文件超过 24 KiB（24,576 字节），且刚取得有记录的阶段性成果时，Codex 才向你建议压缩；得到你同意后执行。** 只有行数超限或尚无阶段性成果时，按需读取历史，不打断研究。阶段性成果包括引理闭合、反例确认、路线有明确结论或论文一轮修订完成；普通增补不算。

提醒会说明项目、当前大小、阶段性成果和整理范围；同一待答提议不重复提醒。你若暂缓，等下一次实质成果或你主动要求再提。你明确要求压缩就直接执行，不重复确认。该规则固定的是提醒流程，不是以后每次自动压缩的许可，也不创建定时监控。

同意后，先将原始字节完整存入项目内的唯一日期存档并校验，再核对目标、假设、状态和阻碍，保留六栏导航，通常整理到约 8–12 KiB；完整性优先于大小。历史失败和完整推导继续保留。`subgoal.md` 优先读取当前分解，旧路线按需检索。详细步骤见 [状态页压缩流程](docs/state_compaction.md)。

下面的只读检查检查六栏结构、大小及本地链接；省略项目名则检查全部登记项目。历史日志大小不作为失败条件，结构检查也不证明数学结论正确。

```powershell
python scripts/check_research_state.py <problem_dir> --check-links
```

## 日常工作流

1. 开始会话时，先读 `research_state.md` 和 `subgoal.md` 当前分解；首次进入、改变范围或假设不明时读 `goal.md` 的精确目标。再读最近 3–5 条完整进度和相关日期笔记，沿当前问题按需检索记忆，避免每次读完整历史。证明审核仍要覆盖全部关键依赖。
2. 讨论数学问题时，要求 Codex 区分“已证明”“合理猜想”“需要验证”“可能错误”。
3. 有重要结论、反例、失败路径或文献线索时，让 Codex 写回当前问题目录下的相应文件；跨两个问题的讨论分别更新，不能混写。
4. 结束前让 Codex 先更新当天笔记、`progress.md` 和相关详细记录，最后刷新 `research_state.md`。

新建问题建议使用脚本，自动创建标准目录、私有状态文件和注册表条目：

```powershell
python .\scripts\create_math_project.py my_math_problem --title "My Math Problem" --role active --description "One-line research objective"
```

创建前需要确定目录名、标题、精确目标与范围、项目角色、说明，以及它和已有问题的关系。如果其中有实质歧义，Codex 会先只读检查并向你询问，不会先创建一个占位目录。

### 脱离当前讨论时的澄清边界

日常数学讨论可以依据紧邻语境理解“这个引理”“刚才的路线”等指代，不要求反复重述。只有当工作要形成独立文件交给其他读者、代理、模型或仓库，跨项目或机器传输，长期运行，或者向外部服务提交时，才必须先固定目标、假设、预期产物、验收条件和执行目的地。

如果这些实质字段存在多种合理解释，Codex 应当针对缺失项反问；澄清前可以只读检查，但不能先生成半成品、委派、传输或提交，也不能静默改成较弱目标或另一种执行方式。当前语境已经唯一确定全部字段且你明确要求开始时，不会重复要求确认。

这一规则也适用于独立证明稿、外部审阅稿、子代理并行和 LaTeX 文稿审阅：目标、读者、输出格式、委派范围、权威源文件或“只诊断/允许修改”边界不清楚时先询问。明确要求子代理但任务不清楚时，不会悄悄退回另一种执行模式。

导出审阅稿、导出给 Lean、交给 Pro/Web Pro 或启动长期自主研究前，Codex 会确认目标、假设、当前状态、交付物、目的地和权限是否清楚；有不确定或互相冲突的地方，就先概括现状并集中问你几句话，答清楚后再执行。日常讨论不受这一规则限制。

### 长时间自主研究（按需启用）

普通讨论不自动进入长时间攻坚模式。需要对一个精确定义的目标进行多轮证明、反例搜索和独立审核时，可以说：

```text
使用 $long-autonomous-math-research，围绕当前问题的这个目标持续研究：……
```

技能首先只读项目状态，向你展示拟冻结的目标、成功标准、执行模式、权限、限制和停止条件。只有你明确确认后才会创建文件并开始研究；如果你已经给出完整契约并明确说“开始”，该消息本身即视为确认。选择持久 Codex goal、子代理、远程计算或外部交接都需要单独明确授权。

每次运行使用独立目录，不再把几十个 wave 追加到 `notes/` 根目录的一个文件：

```text
<problem_dir>/notes/autonomous_runs/<run_id>/
├── contract.md
├── index.md
├── checkpoint.md
├── waves/
├── audits/
└── artifacts/
```

`contract.md` 保存冻结契约，`index.md` 每个 wave 只保留一行索引，`checkpoint.md` 保存当前阻碍和恢复动作，每个详细 wave 单独写入 `waves/`。可复用数学结论仍进入原有 `memory/`，项目当前状态仍以 `research_state.md` 为准，不建立第二套研究状态。旧的 `notes/autonomous_run_*.md` 保持只读兼容，不会自动迁移或继续追加。

新运行标记 `Run format version: 2`。无版本或版本 1 的旧目录按历史格式检查，兼容旧文件名和状态标签；检查通过不代表旧结论被重新认证，也不授权恢复。检查点落后于实际 wave 仍报错。旧目录继续研究时，保留原契约和记录，在目标及授权明确后建立版本 2 的独立续接运行。

恢复前要对照冻结契约、项目当前目标、子目标、检查点和最新 wave，尤其检查撤回结论及用户暂停。新格式检查点保存这次核对说明和来源指纹；`--print-context <run_id>` 只打印指纹，`--resume-run <run_id>` 检查来源是否变化及运行是否允许恢复。两者都接在下面命令的项目名之后，均只读。不能只刷新指纹来绕过内容核对。

只要成功标准尚未达到、用户没有明确暂停、也不存在真正的权限或外部环境阻碍，运行就必须保持 `active` 并进入下一 wave。当前路线困难、需要证明新定理、完成固定范围计算或已经运行很多 waves 都不是停止条件。单次任务因产品或上下文边界结束时记为 `interrupted_runtime`，不能写成研究暂停或完成；如果你要求跨任务持续运行，需要在契约中明确选择并授权 `persistent-goal`。

可以随时检查新格式运行目录：

```powershell
python .\scripts\check_autonomous_runs.py <problem_dir>
```

## 只读研究仪表盘

需要同时查看多个问题的当前目标、下一步、开放义务和 Pro 中转状态时，可以按需启动本地 Desktop 仪表盘：

Windows 下可直接双击项目根目录的 `start_reader.cmd`。它使用项目的 `.venv`、自动选择空闲端口并在默认浏览器中打开带临时令牌的阅读器；关闭其控制台窗口或按 `Ctrl+C` 即停止服务。

也可以从命令行启动：

```bash
./.venv/Scripts/python.exe ./scripts/research_dashboard.py
```

命令会输出一个带临时会话令牌的 `http://127.0.0.1:8765/` 地址。仪表盘直接读取 `projects.json`、各问题的 `research_state.md`、日期笔记文件名和 `handoff/manifest.json`，不会创建数据库或修改研究文件。

点击项目进入六栏状态详情；状态页中已有的 Markdown 相对链接可直接打开。普通 Markdown 可在仪表盘内格式化显示并切换源码；生成的 `*.reader.md` 会列在 Files 页的 Reading copies 区域，并在独立阅读窗口中打开。阅读窗口带有可折叠目录，默认列出章节和小节、随正文滚动高亮当前位置，并可按需显示定理、命题与定义等陈述书签。生成器保留 TeX 枚举的罗马数字、字母及括号样式，并自动展开源稿中不带参数的 `\newcommand` 数学宏；定理类、定义类和注记类环境以克制的浅色条带区分，证明保持正文底色并在末尾显示清晰的证毕方块。阅读稿的本地文献链接优先在另一个窗口打开 PDF；带定理、命题、定义或章节定位的引文会尽可能直接跳到对应 PDF 页。数学公式由项目内自托管的 KaTeX 渲染 `\(...\)`、`\[...\]`、`$...$` 和 `$$...$$`；TeX 和其他文本文件使用带行号的只读源码视图，PDF 使用浏览器内置阅读器。服务只监听本机地址，按 `Ctrl+C` 停止。

独立阅读窗口右上角的 `⇩` 会让本地阅读器进程直接在当前项目的 `exports/` 中生成完整离线阅读包，同时保留 ZIP 和已解压目录。它不再经过浏览器附件下载，因此 Windows 不会因本地 HTTP 下载而给输出附加 Internet 安全标记。离线包包含预渲染的 `index.html`、原始 `source.reader.md`、正式 TeX 入口、审阅稿 PDF、该阅读副本实际链接到的本地参考文献 PDF、KaTeX 字体和带哈希的 `manifest.json`；直接打开解压目录中的 `index.html`，不需要启动本地服务或联网。导出器会拒绝过期的阅读副本、公式错误、缺失 PDF、越出项目的链接和任何无关的已有输出；按钮只会安全更新它自己之前生成的阅读包。也可以从命令行生成并保留解压目录：

```powershell
python .\scripts\export_reader_bundle.py <problem_dir>\notes\proof.reader.md --keep-directory
```

## 跨电脑迁移单个问题

公开仓库代码照常通过 GitHub clone/pull；被 Git 忽略的私有研究状态使用问题包单独迁移：

```powershell
python .\scripts\problem_bundle.py export example_math_problem --dry-run
python .\scripts\problem_bundle.py export example_math_problem
python .\scripts\problem_bundle.py export example_math_problem --inbox inbox\额外材料.md
python .\scripts\problem_bundle.py inspect .\tmp\problem_bundles\<bundle>.zip
```

导出器会自动包含该问题 Markdown 中明确引用且实际存在的 `inbox/` 文件；`--inbox` 只用于补充尚未被引用的材料，不会打包整个 inbox。在另一台电脑 clone 仓库后，先预演再恢复：

```powershell
python .\scripts\problem_bundle.py restore D:\private-transfer\<bundle>.zip --dry-run
python .\scripts\problem_bundle.py restore D:\private-transfer\<bundle>.zip
```

恢复前会完整验证清单、文件大小和 SHA-256；默认遇到不同内容的现有文件就停止，并保证零写入。压缩包未加密，不应通过公开渠道传输未公开研究。完整范围、冲突策略和安全说明见 [Portable Private Problem Bundles](docs/problem_bundle.md)。

如果导出/恢复对象、附带的 `inbox/` 材料、输出或目标位置、冲突策略、传输渠道不清楚，Codex 会先执行必要的只读检查或 dry-run，再向你确认；不会在歧义仍存在时创建、恢复、覆盖或传输问题包。

## 网页端 Pro 中转

Pro 只在网页端可用时，使用当前问题目录内的 `handoff/` 把本地整理和网页讨论分开。脚本不会打开网页，也不会自动提交；你仍然手动上传初始上下文，并在讨论结束后保存最终交接稿。

导出前需要确定具体问题及假设、它在总目标中的位置、期待 Pro 返回的产物、允许路线、禁止替代、验收标准和上下文范围。如果任何一项有多种合理解释，Codex 会先反问且不生成临时任务包。明确要求生成本地任务包不等于授权浏览器提交。

让 Codex 自动执行时，可以直接说：

```text
把当前这个精确子问题导出给 Pro，并加入相关的失败路径作为上下文。
```

也可以手动导出。短问题直接写在命令中：

```powershell
python .\scripts\pro_handoff.py export example_math_problem --question "要 Pro 解决的精确问题" --slug sample-lemma --user-authorized
```

较长或包含复杂 LaTeX 的问题适合先写成 UTF-8 Markdown，再导出：

```powershell
python .\scripts\pro_handoff.py export example_math_problem --question-file .\inbox\pro_question.md --context memory\failed_paths.md --user-authorized
```

生成文件位于：

```text
<problem_dir>/handoff/requests/<task_id>.md
```

把该文件上传到网页端 Pro，随后可以正常进行多轮讨论、追问、修正和分支探索。任务包不会要求 Pro 在第一轮就按固定格式回答。它默认包含状态页、目标、进展、子目标和最近日期笔记；`--context` 可以重复使用，只能加入当前问题目录内的文件。

准备结束网页讨论时，对 Pro 说：

```text
请根据初始任务文件里的 Final Research Handoff Contract，整理一份最终交接稿。综合整个对话，明确区分已证明、条件性结论、合理猜测、待验证步骤和失败路线。只输出完整 Markdown 交接稿。
```

把这份最终交接稿不作修改地保存为 UTF-8 Markdown，然后导入：

```powershell
python .\scripts\pro_handoff.py import example_math_problem <task_id> .\inbox\pro_answer.md
```

导入会保存原始回答、计算校验值，并在 `<problem_dir>/handoff/reviews/` 生成审核清单。它不会自动修改任何研究状态。接下来可以对 Codex 说：

```text
审核刚导入的 Pro 回复。先核对证明、假设和引用，再把确认后的内容写入当前问题记录。
```

审核和研究记录更新完成后：

```powershell
python .\scripts\pro_handoff.py review example_math_problem <task_id> --summary "审核结论"
python .\scripts\pro_handoff.py status example_math_problem
```

每个问题的 `handoff/` 中除 `.gitkeep` 外的所有内容都被 Git 忽略，并由公开范围检查阻止提交。不指定问题运行 `status` 时，会汇总扫描 `projects.json` 中的所有项目。

跨问题讨论、尚未确定归属的材料和外部研究报告应放入根目录 `inbox/`。Codex整理后会分别更新受影响的问题目录，并保留 `inbox` 原稿作为本地来源；`inbox` 不作为任何问题的长期状态页。

## 导出给 Lean 验证

Lean 验证使用由 `--lean-root` 显式指定的独立工程，不把它登记为数学问题，也不复制进本仓库；不要把某台机器的 Lean 路径固化进项目文件。只有已经通过自包含证明资格门槛的闭合文稿才允许导出：每个本地引理均已证明，重要外部结果的陈述、来源、假设和适用性均已核对，所有构造和过渡均已论证，不存在仍为 `plausible`、`needs verification`、依赖未证明局部结论或其他未决步骤的内容。此外还必须有针对该完整文稿的无已知缺口内部审计、你的明确导出要求、精确结果及假设，以及完全 `sorry`-free 或允许精确引用外部标准结果的政策。条件不满足时回到研究流程，不生成形式化包。

交接包位于：

```text
<problem_dir>/handoff/formalization/exports/<task_id>/
```

导出输入分为两层：`--review-proof-file` 指向唯一的未拆分闭合审阅稿（Markdown 或 TeX），重复的 `--unit-file` 指向从该文稿拆出的、依赖有序且可独立形式化的小单元。每个单元使用独立的 `UpperCamelCase.md` 文件，并具有非空的 `Statement`、`Assumptions`（可明确写 `None`）、`Proof steps` 与 `Dependencies` 四节；依赖用 `Local:`/`External:` 行结构化声明。本地依赖只能指向更早单元，外部依赖使用 `[@引用键]`，并对应权威 `References.md` 中的精确条目。

`documented-external-results` 要求通过 `--reference` 提供作者、标题、版本/年份、稳定标识或 URL、定理/章节/页码/公式定位，以及 `Local source path`。已经下载到当前问题目录的权威文献必须写问题相对路径；导出器会校验文件、将其纳入源漂移检查，并在 `References.md` 写入相对路径、导出时绝对路径、大小和 SHA-256，使同一机器上的 Lean 侧优先直接打开本地副本而不重复搜索下载。确无本地副本时才写 `Not downloaded`；文献文件本身不复制进 Lean 仓库。`sorry-free` 且确无外部引用时会生成明确的 not applicable。结构化 ledger 必须逐行匹配单元顺序、依赖和计划模块；`--lean-task-module <UpperCamelCase>` 显式区分同一问题的不同结果或修订。`--proof-closed-for-review`、`--audit-no-known-gaps` 和 `--user-authorized` 只记录已完成人工判断的门槛，不能替代状态核对或数学审核。数学项目中的导出记录包含 `Index.md`、`References.md`、完整证明、`Units/*.md` 及仅供本项目校验的根级 manifest。导出后先校验，再显式暂存到 Lean 工程：

```powershell
python .\scripts\formalization_handoff.py verify <problem_dir> <task_id>
python .\scripts\formalization_handoff.py stage <problem_dir> <task_id> --lean-root <lean_root>
```

暂存到 Lean 侧的权威输入位于 `informal/<problem_dir>/Tasks/<task_id>/`，严格包含 `Index.md`、`References.md`、`Proof.md` 或 `Proof.tex`、以及 `Units/*.md`；数学项目的 manifest 不随之复制。同一问题始终只有一个总文件夹，不同结果或修订各占不可变任务目录；工具拒绝覆盖已有任务，也拒绝与其他任务冲突的计划 Lean 模块。旧的未版本化输入保持原位，不自动迁移；旧 schema 导出如需再次交接，应从已审计源新建 schema 2 任务，不能改写旧包。

至此研究项目的交接职责结束。Lean 侧先按 `References.md` 的精确定位自行核查疑点；若确认数学错误、引用错误、关键资料缺失或仍无法消除关键歧义，必须停止并向用户给出精确阻塞报告。不得自动向研究侧建立提问/回写通道，不得修改已交接证明、猜测替代命题、弱化目标或自动生成“修正版”研究结论。正式 Lean 模块、迭代记录、构建审计和完成判定全部由 Lean 项目按其当前指令与目录结构管理。本项目不创建其工作流目录、不打包返回结果，也不提供导入命令。完整流程由 `skills/formalization-handoff/SKILL.md` 管理。

收尾提示词：

```text
请收尾：
1. 更新今天的日期笔记；
2. 更新 progress.md；
3. 如果有新的子目标或失败路径，更新 subgoal.md 或 memory/；
4. 根据上述详细记录刷新 research_state.md；
5. 用三句话总结今天完成了什么、还卡在哪里、下次从哪里开始。
```

## 默认本地搜索

Codex 默认采用以下顺序，不会主动启动 LanceDB、Ollama 或嵌入模型：

```text
项目 memory/、日期笔记和 notes/
→ arXiv 文章强制获取版本匹配的源码包
→ 搜索主 TeX
→ 源码确实不可用时才搜索 PDF 提取 TXT，并记录原因
→ 回到 PDF 或正式发表版本核对
→ 阅读指定论文：本地资料不足时联网
→ 文献调研：即使本地已有资料也继续联网
```

先搜索项目记忆：

```powershell
rg --no-ignore -n -i "Noetherian rings" .\example_math_problem\memory .\example_math_problem\notes -g "*.md" -g "!**/.lancedb/**" -g "!**/*.lancedb/**"
```

查阅 arXiv 论文时，即使本地已经有 PDF 或提取 TXT，也必须先获取所用 arXiv 版本对应的源码包，解压到当前问题的 `refs/sources/`，并确定主 `.tex` 文件。随后优先搜索主 `.tex`：

```powershell
rg --no-ignore -n -i "Noetherian rings" .\example_math_problem\refs -g "*.tex" -g "!**/.lancedb/**" -g "!**/*.lancedb/**"
```

只有源码包不可获取、不含可用 TeX、源码不完整、无法可靠解码或不能形成忠实的可搜索表示时，才搜索 PDF 提取的 TXT：

```powershell
rg --no-ignore -n -i "Noetherian rings" .\example_math_problem\refs -g "*.txt" -g "!**/.lancedb/**" -g "!**/*.lancedb/**"
```

问题目录中的研究资料被 Git 主动忽略，因此这里必须使用 `--no-ignore`；命令应限制在当前问题目录内，并排除 LanceDB 等生成目录。

上述例外必须在 `refs/catalog.json` 的 `notes` 中记录具体原因和尝试的 arXiv 版本；只有这种情况下，arXiv 条目的 `tex_main` 才可以是 `null`。同一论文同时存在 TeX 和提取 TXT 时，默认不把它们当作两个独立来源，也不同时搜索。TeX 适合发现定理和公式；重要陈述、编号、页码及版本差异应回到 PDF 或正式发表版本核对。对于指定论文的阅读任务，本地资料不足时再使用 arXiv、LeanSearch、Matlas 或网页搜索。

### 阅读与文献调研

Codex 会区分两种任务：

- **阅读指定论文或核对已知结果：** 先按 TeX → TXT 后备 → PDF 核对的本地顺序查阅；缺少准确上下文、权威版本或被引用来源时再联网。
- **文献调研：** 当你要求查找相关结果、研究现状、后续工作、新颖性或最新版本时，本地材料只用于提取术语、作者和引用线索，即使已经存在相关 PDF 或 TeX，也会继续联网搜索。

本地参考文献是阅读缓存和研究记忆，不是联网检索的边界。明确提出“联网搜索”“查最新文献”“核对当前研究现状”或“寻找更新工作”时，Codex 必须联网，不会因为本地已有材料而停止。

下载和整理文献时，按 [参考文献工作流](docs/reference_workflow.md) 维护 `refs/catalog.json`，记录 arXiv 版本、主 TeX、TXT 后备、PDF、来源和 SHA-256。对 arXiv 文章，版本匹配的源码获取是必做步骤，不是可选优化。目录结构和元数据可以用以下命令检查：

```powershell
python .\scripts\check_reference_catalog.py .\<problem_dir>\refs\catalog.json --check-files
```

## 可选语义索引（仅手动触发）

LanceDB + Ollama 流程完整保留，但 Codex 只有在你明确要求“本地语义搜索”“使用 LanceDB/Ollama”“生成嵌入”或“构建/更新索引”时才会运行。普通的“查资料”“搜索文献”或“继续研究”不会触发它。

`search_references.py` 用于搜索 `refs/` 下的 `.md`、`.tex`、`.txt` 文件。它会递归收集文本文件，并跳过 LanceDB 索引目录。

手动运行该脚本时，它会尝试使用 LanceDB + Ollama 做语义搜索；如果 Ollama 不可用，会回退到关键词搜索。除非明确需要，不要使用 `--force`，以保留现有增量索引流程。

```powershell
python .\search_references.py .\example_math_problem\refs "Noetherian rings" --top_k 5
```

跳过索引构建，直接搜索现有索引或关键词 fallback：

```powershell
python .\search_references.py .\example_math_problem\refs "localization" --no-build
```

强制重建索引：

```powershell
python .\search_references.py .\example_math_problem\refs "prime ideal" --force --verbose
```

一行一个 JSON 结果，方便脚本处理：

```powershell
python .\search_references.py .\example_math_problem\refs "ring homomorphism" --jsonl
```

禁用关键词 fallback；如果语义搜索不可用则报错：

```powershell
python .\search_references.py .\example_math_problem\refs "polynomial ring" --no-fallback
```

## arXiv 定理搜索

`search_arxiv_theorems.py` 调用外部定理搜索服务，用来找相关定理、引理和定义。默认先用 LeanSearch；如果 LeanSearch 不可访问，会自动回退到 Matlas。

```powershell
python .\search_arxiv_theorems.py "Noetherian ring localization flat" --num 10
```

也可以指定服务：

```powershell
python .\search_arxiv_theorems.py "Noetherian ring localization flat" --provider matlas --num 10
python .\search_arxiv_theorems.py "Noetherian ring localization flat" --provider leansearch --num 10
```

返回 JSON 里会包含实际使用的 `provider` 和可能的 `fallback_errors`。这个脚本需要网络和外部服务可用，适合在本地资料不足或进行文献调研时使用。

## 可选索引依赖

本地语义搜索依赖：

- Python
- `requests`
- `lancedb`
- `pyarrow`
- Ollama 服务
- Ollama 模型：`nomic-embed-text:latest`

安装基础联网搜索依赖：

```powershell
python -m pip install -e .
```

明确需要本地语义索引时再安装可选依赖：

```powershell
python -m pip install -e ".[semantic]"
```

如果 Ollama 不可用，`search_references.py` 默认会退回关键词搜索；结果中会出现：

```json
{"search_type": "keyword"}
```

## 可选语义索引 Python API

可以在脚本或 Codex 会话中直接使用：

```python
from reference_index import ReferenceIndex

idx = ReferenceIndex(r"C:\math-workspace\example_math_problem\refs")
idx.build()
results = idx.search("localization", top_k=5, fallback=True)
```

关键词 fallback：

```python
results = idx.keyword_search("prime ideal", top_k=5)
```

## 记录规范

建议这样分配内容：

- 当前问题的 `Research State`、`Known Theorems`、`Open Problems`、`Failed Attempts`、`Current Goal`、`References`：`<problem_dir>/research_state.md`
- 当天讨论、灵感、临时推导：`<problem_dir>/YYYY-MM-DD.md`
- 总体进展：`<problem_dir>/progress.md`
- 当前证明路线：`<problem_dir>/subgoal.md`
- 失败证明：`<problem_dir>/memory/failed_paths.md`
- 反例：`<problem_dir>/memory/counterexamples.md`
- 简单例子：`<problem_dir>/memory/toy_examples.md`
- 文献搜索：`<problem_dir>/memory/search_results.md`

## 注意事项

- 不要只把关键数学内容留在聊天里，重要内容要写入文件。
- 如果 Codex 给出强结论，要求它列出使用的假设。
- 如果某一步依赖文献，要求记录来源和适用条件。
- 对重要证明，至少做一次反例尝试和一次逐段检查。
- `search_references.py` 没有项目级 `problem-id` 参数；目前按目录组织项目。

提交框架更新前，检查暂存区没有研究正文、PDF、TeX 源码包或索引：

```powershell
python .\scripts\check_public_scope.py
```

检查仓库目前全部已跟踪文件：

```powershell
python .\scripts\check_public_scope.py --tracked
```

可选地启用仓库自带的 pre-commit hook，让每次提交自动执行暂存区检查：

```powershell
git config core.hooksPath .githooks
```

运行全部离线测试和注册表检查：

```powershell
python -m unittest discover -s .\tests -v
python .\scripts\check_project_registry.py
```
