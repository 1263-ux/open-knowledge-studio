# Office 输出技能调研记录（2026-08-26）

## 目标

为 OKS 增加一个统一的 `office` 输出技能：同一份召回后的、带来源台账的知识，按需要生成 Word、PDF、PowerPoint；不把输出内容回写到 Wiki。

## 调研方法

- Firecrawl：搜索并读取官方文档、开发者索引，确认生成库的能力边界。
- 通用网页检索：对官方文档和版本信息做交叉核验。
- Tavily：当前 Codex 工具目录没有可调用的 Tavily tool，未伪造调用；该环境事实应在后续接入测试中重新确认。

## 主要发现

1. `python-docx` 适合创建和更新 `.docx`，并以段落、样式、表格等结构化对象控制内容；模板应作为现有文档打开，而不是把模板当成纯文本替换。
2. `python-pptx` 适合跨平台创建和更新 `.pptx`，但 PowerPoint 格式能力很宽，复杂主题、动画和高级布局不能由“文件成功保存”推断为视觉正确，必须逐页渲染验收。
3. ReportLab 的 Platypus 将文档模板、页面模板、Frame、Flowable 和内容分开，适合直接生成 PDF；中文 PDF 需要显式注册可用字体，否则可能出现字形缺失。
4. LibreOffice 官方命令行过滤器可以执行 Office 到 PDF 的转换，但它是转换/互操作边界，不是知识选择器，也不能替代源文件与最终 PDF 的视觉回读。
5. OKS 已有 `office.markitdown` 能力清单，但它描述的是 Office 文件解析为 Markdown；不能将它误认为“知识生成 Office”的能力。

## 方案决策

- 统一输入：一个 JSON outline，包含 `title`、`sections`、`sources`。
- 统一证据链：Recall → 完整 Wiki/Raw 阅读 → source ledger → outline → format adapter → render/inspect。
- 输出适配器：Word 使用 `python-docx`/既有 `knowledge-to-word` builder；PDF 使用 ReportLab；生产级 PPT 遵循 `presentations` skill 的 artifact-tool 路径，`python-pptx` 仅作为便携冒烟适配器；LibreOffice 只在明确需要转换时使用。
- 兼容性：保留 `knowledge-to-word` 作为 Word-only 入口，新增 `office` 作为多格式入口。
- 验收：每一页/每一张幻灯片都要渲染检查；未能渲染时明确记录 `visual_qa: unavailable`。

## 本轮验证记录

- `C:\Users\chenfeng\AppData\Local\Programs\Python\Python314\python.exe -X utf8 C:\Users\chenfeng\.codex\skills\.system\skill-creator\scripts\quick_validate.py assets/skills/office`：PASS。
- `C:\Users\chenfeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m py_compile assets/skills/office/scripts/build_office.py assets/skills/knowledge-to-word/scripts/build_docx.py`：PASS。
- `C:\Users\chenfeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest assets/skills/office/tests/test_build_office.py`：PASS；覆盖 source refs、source 字段、`0/False` 保真、不规则表格、中文 PDF 字体门禁和 PPT 长文本分片。
- 在仓库根目录执行以下实际生成命令：

  ```powershell
  $py = "C:\Users\chenfeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  & $py assets/skills/office/scripts/build_office.py --outline tmp/office-smoke-outline.json --format docx --output tmp/office-smoke.docx
  & $py assets/skills/office/scripts/build_office.py --outline tmp/office-smoke-outline.json --format pdf --output tmp/office-smoke.pdf
  & $py assets/skills/office/scripts/build_office.py --outline tmp/office-smoke-outline.json --format pptx --output tmp/office-smoke.pptx
  & $py -c "from docx import Document; from pypdf import PdfReader; from pptx import Presentation; d=Document('tmp/office-smoke.docx'); p=PdfReader('tmp/office-smoke.pdf'); s=Presentation('tmp/office-smoke.pptx'); print({'docx_paragraphs':len(d.paragraphs),'pdf_pages':len(p.pages),'pptx_slides':len(s.slides),'status_in_docx':any('[reviewed]' in x.text for x in d.paragraphs),'status_in_pdf':'[reviewed]' in ''.join(page.extract_text() or '' for page in p.pages),'status_in_pptx':any('[reviewed]' in sh.text for sl in s.slides for sh in sl.shapes if hasattr(sh,'text'))})"
  ```

  结果：PASS；同一份带 `source_refs` 的 outline 生成三种格式，来源台账和 status 均保留。
- 旧 Word builder 实际回归命令：

  ```powershell
  $py = "C:\Users\chenfeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  & $py assets/skills/knowledge-to-word/scripts/build_docx.py --outline tmp/legacy-status-outline.json --output tmp/legacy-status.docx
  & $py -c "from docx import Document; d=Document('tmp/legacy-status.docx'); print(any('[partial]' in p.text for p in d.paragraphs))"
  ```

  结果：PASS；旧 Word builder 的 Sources 条目保留 status。
- 缺少标题、sources、section `source_refs`、未知 source id 或不规则 table：均拒绝生成。
- `visual_qa: unavailable`：当前环境没有 LibreOffice/soffice；PPTX artifact-tool 渲染入口也在运行时失败，因此本轮只报告结构/生成验证，不宣称页面或幻灯片视觉通过。

## 参考来源

- [python-docx 官方文档](https://python-docx.readthedocs.io/en/latest/)
- [python-docx 官方 Quickstart](https://python-docx.readthedocs.io/en/stable/user/quickstart.html)
- [python-pptx 官方文档](https://python-pptx.readthedocs.io/en/latest/)
- [python-pptx Presentation API](https://python-pptx.readthedocs.io/en/stable/api/presentation.html)
- [ReportLab Platypus 官方文档](https://docs.reportlab.com/reportlab/userguide/ch5_platypus/)
- [LibreOffice PDF 导出参数](https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html)
- [LibreOffice 文件转换过滤器](https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html)

## 外部案例复查与吸收

上一版调研偏重底层库官方文档，不能支撑“专属工作流已经吸收社区最佳实践”的结论。本轮补查 GitHub、开发者项目和转换问题记录，选取代表性实现而不是照搬代码：

- [Anthropic Skills](https://github.com/anthropics/skills)：官方将 DOCX、PDF、PPTX 分成独立技能；PPTX 路径包含模板缩略图、布局/设计系统、speaker notes、OOXML 校验和逐 slide 渲染检查，并明确避免通用装饰线与“能保存即正确”。
- [tfriedel/claude-office-skills](https://github.com/tfriedel/claude-office-skills)：以 Office 套件组织格式专属指南和脚本，证明格式路由应在共享内容契约之后，而不是让一个脚本承担所有视觉决策。
- [ferdinandobons/brand-docs](https://github.com/ferdinandobons/brand-docs)：采用 `extract → comprehend → verify → generate`，学习既有 Word/PowerPoint 模板的 profile，默认视觉 QA，并在 QA 通过后原子发布；这被吸收为 OKS 的 template-first 边界。
- [tobias-bettinger/ppt-agent](https://github.com/tobias-bettinger/ppt-agent)：使用 `research → outline → content → design → deterministic builder → visual QA loop` 的类型化流水线；这被吸收为“先证据包，后格式适配”，而不是三次独立写作。
- [Docling issue #3819](https://github.com/docling-project/docling/issues/3819) 与 [fix #3820](https://github.com/docling-project/docling/pull/3820)：LibreOffice 转换需要 timeout 与隔离 profile，否则可能挂起、锁 profile 或静默丢失图表/图片；因此 OKS 不把无边界的 headless conversion 当作成功条件。
- [GitHub document-generation topic](https://github.com/topics/document-generation)：社区实现数量足以说明需求成熟，但质量和职责差异很大，不能以仓库数量替代结构化验收。

### 设计增量

1. 新增 `oks-office-evidence/v1`：Recall 结果、claims、claim-to-source、section blocks、模板请求和 source status 进入单一证据包。
2. 新增 fail-closed validator/preflight：未知 id、无来源 claim、不规则表格、非法 status、中文 PDF 缺字体均在 authoring 前拒绝。
3. 新增 package → shared outline 归一化：DOCX/PDF/PPTX 共享同一事实输入，旧 outline 继续兼容。
4. 新增 template-first、production adapter、portable smoke、structural QA、visual QA、atomic publish 的边界说明。
5. 明确生产 PPTX 走 `presentations` skill；Python fallback 仅证明序列化和证据不丢失，不再以当前 smoke 截图代表最终设计质量。

## 本轮 OKS 专属工作流验收补充

- `assets/skills/office/tests/test_build_office.py` 与 `test_evidence_package.py`：最终 13/13 PASS（可选渲染依赖缺失时，三格式回读测试明确 skip；bundled runtime 下实际执行）。
- `quick_validate.py assets/skills/office`（Python 3.14 runtime）：PASS；脚本 `py_compile`、`--help` 和 `git diff --check`：PASS。
- `validate_evidence_package.py`：fixture PASS，并成功写出 normalized outline；`office_preflight.py`：带 `C:\Windows\Fonts\simhei.ttf` 时三种格式均 ready，不带字体时中文 PDF 以 exit 1 fail-closed。
- `build_office.py --package` 实际生成 DOCX/PDF/PPTX 并结构回读：DOCX 10 paragraphs、PDF 1 page、PPTX 5 slides；三者均保留 `[reviewed]` 和 `[sources: src-1]`。
- 视觉 QA：documents `render_docx.py` 实际运行失败，原因是环境没有 `soffice`；PPTX artifact-tool/LibreOffice 仍不可用。因此本轮结论是结构与证据链 PASS，`visual_qa: unavailable`，不是视觉验收通过。
- fresh agent 首轮指出的 P1（表格来源/多表格覆盖）与 P2（状态丢失、缺少三格式回读）已修复；增量复核最终 PASS，无 P1/P2 残留。

## Word 生产层吸收补充

- Firecrawl connector 复查了 BrandDocs 与 DOCX skill 资料；BrandDocs 的公开仓库声明 MIT，采用 `extract → verify → generate`、portable Brand Profile、profile-only style resolution 和 QA gate。
- Anthropic 官方 DOCX skill 标注为 proprietary，因此没有复制其代码或资源；只吸收公开可验证的工程规则：DOCX 是 OOXML zip、表格使用固定 DXA 双宽度、明确 shading、重复表头、结构校验和渲染后检查。
- 新增 `oks-word/v1` profile、`extract_word_profile.py`、`validate_docx.py`，并将默认 DOCX builder 从 Word 内置 `Light Shading Accent 1` 改为显式 OKS 表格设计：固定宽度、深色表头、斑马纹、边框、内边距、数字对齐、重复表头和证据注释。
- 实际 profile round-trip：从 `tmp/oks-office-package.docx` 提取 profile，再生成 `tmp/oks-office-package-profiled.docx`；结构校验 PASS，2 tables、3 rows/2 columns、2880 DXA 首列宽度、Evidence note 均读回。
- `render_docx.py` 对改进后 DOCX 的视觉渲染仍因 `soffice=unavailable` 失败；结论仍是 structural QA PASS、`visual_qa: unavailable`。
