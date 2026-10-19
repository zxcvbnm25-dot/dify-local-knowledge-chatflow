"""从公开 DSL 生成学习文档和流程图；不执行工作流，也不读取环境变量。"""
from __future__ import annotations

import copy
import re
import textwrap
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DSL = ROOT / "local_knowledge_chatflow.yml"
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"

SECTIONS = [
    ("section-01", "01｜本轮附件", "先把本轮附件变成可供理解的临时上下文", [
        "start", "has_attachments", "attachment_iteration", "attachment_iteration_start",
        "classify_attachment", "attachment_is_image", "attachment_vision_llm",
        "attachment_document_extractor", "attachment_content", "pack_attachment_result",
        "format_attachment_context", "no_attachment_context", "attachment_context",
    ]),
    ("section-02", "02｜检索计划", "把问题收敛成可检索的请求，必要时只追问一次", [
        "query_rewrite", "query_guard", "clarification_gate", "clarification_answer",
    ]),
    ("section-03", "03｜检索与服务故障", "请求 bridge 并区分空资料与检索服务异常", [
        "build_knowledge_request", "fetch_knowledge", "knowledge_retrieval", "retrieval_gate",
        "retrieval_unavailable", "pack_candidates",
    ]),
    ("section-04", "04｜证据筛选与校验", "只保留可逐字核对、能回答当前问题的证据", [
        "evidence_filter_llm", "validate_evidence_filter",
    ]),
    ("section-05", "05｜关联原图解读", "按已校验的检索问题查图，下载成功后才送入视觉模型", [
        "build_related_images_request", "related_images", "parse_related_images", "prepare_image_input",
        "image_vision_iteration", "image_vision_iteration_start", "download_image",
        "verify_image_download", "fail_image_download", "vision_llm", "pack_image_result",
        "format_image_results",
    ]),
    ("section-06", "06｜回答与引用输出", "依据已验证文字证据生成回答，并校验引用后输出", [
        "answer_llm", "format_grounded_answer", "answer",
    ]),
]

SECTION_BY_NODE = {node: key for key, _, _, nodes in SECTIONS for node in nodes}
TYPE_CN = {
    "start": "开始", "if-else": "条件分支", "iteration": "迭代", "iteration-start": "迭代开始",
    "llm": "模型", "document-extractor": "文档提取", "variable-aggregator": "变量汇总",
    "code": "代码", "http-request": "HTTP 请求", "answer": "回复",
}

SHORT = {
    "start": ("请求开始", "无", "sys.query / sys.files"),
    "has_attachments": ("检查本轮文件", "sys.files", "有附件 / 无附件"),
    "attachment_iteration": ("串行遍历附件", "sys.files", "每项读取结果"),
    "attachment_iteration_start": ("进入单个附件", "当前附件", "循环内起点"),
    "classify_attachment": ("识别附件类型", "type / MIME / 扩展名", "kind"),
    "attachment_is_image": ("按 kind 分支", "classify_attachment.kind", "图片 / 文档"),
    "attachment_vision_llm": ("提取图片可见事实", "图片 + 用户问题", "JSON 观察"),
    "attachment_document_extractor": ("提取文档正文", "当前附件", "text"),
    "attachment_content": ("合并两类读取结果", "视觉 / 文档 text", "output"),
    "pack_attachment_result": ("封装单个附件", "文件名 + content", "result"),
    "format_attachment_context": ("合并附件上下文", "迭代输出", "context"),
    "no_attachment_context": ("提供空上下文", "无", "context = 空"),
    "attachment_context": ("合并两条附件分支", "有 / 无附件 context", "output"),
    "query_rewrite": ("生成检索计划", "问题 + 附件上下文", "JSON 计划"),
    "query_guard": ("验证检索计划", "模型 JSON + 原问题", "query / 澄清标记"),
    "clarification_gate": ("判断是否澄清", "needs_clarification", "追问 / 检索"),
    "clarification_answer": ("输出澄清问题", "clarification_question", "回答"),
    "build_knowledge_request": ("构造检索请求", "query", "request_body"),
    "fetch_knowledge": ("调用 bridge 检索", "请求体 + 密钥", "status_code / body"),
    "knowledge_retrieval": ("解析检索响应", "HTTP 状态 + body", "result / retrieval_ok"),
    "retrieval_gate": ("判断检索是否成功", "retrieval_ok", "候选 / 服务异常"),
    "retrieval_unavailable": ("说明服务异常", "retrieval_notice", "回答"),
    "pack_candidates": ("编号检索候选", "检索 records", "candidates_json"),
    "evidence_filter_llm": ("选择逐字证据", "候选 + 问题", "selected JSON"),
    "validate_evidence_filter": ("校验证据摘录", "候选 + selected", "已验证证据"),
    "build_related_images_request": ("构造查图请求", "已校验 query", "request_body"),
    "related_images": ("调用 bridge 查图", "请求体 + 密钥", "status_code / body"),
    "parse_related_images": ("解析图片记录", "HTTP 状态 + body", "images / notice"),
    "prepare_image_input": ("验证图片输入", "images / notice", "可迭代 images"),
    "image_vision_iteration": ("串行遍历原图", "images", "每图解读"),
    "image_vision_iteration_start": ("进入单张原图", "当前图片", "循环内起点"),
    "download_image": ("下载原图", "当前图片 URL", "status_code / file"),
    "verify_image_download": ("验证下载状态", "download 状态", "成功 / 失败"),
    "fail_image_download": ("记录下载失败", "status_code", "failure"),
    "vision_llm": ("解读知识库原图", "下载图片 + 问题", "text"),
    "pack_image_result": ("绑定原图 ID", "当前图片 + 视觉 text", "result"),
    "format_image_results": ("汇总图片解读", "images + 迭代结果", "markdown / context"),
    "answer_llm": ("根据证据起草答案", "问题 + 已验证证据", "JSON 答案"),
    "format_grounded_answer": ("校验引用并排版", "答案 + 验证证据", "answer_text / sources_markdown"),
    "answer": ("回复用户", "正文 + 图片 + 来源", "最终回答"),
}

def font(size: int):
    return ImageFont.truetype(FONT, size)

def selector(value):
    return ".".join(map(str, value)) if isinstance(value, list) else str(value)

def yaml_text(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110).rstrip()

def short_lines(text: str, width: int, max_lines: int):
    lines = []
    for source in str(text or "").splitlines() or [""]:
        lines.extend(textwrap.wrap(source, width=width, break_long_words=True, break_on_hyphens=False) or [""])
    return lines[:max_lines]

def draw_text(draw, xy, text, fnt, fill, max_width=None, line_gap=6):
    x, y = xy
    lines = [text]
    if max_width:
        # Chinese wraps best by measured characters rather than whitespace.
        lines, current = [], ""
        for char in str(text):
            candidate = current + char
            if current and draw.textlength(candidate, font=fnt) > max_width:
                lines.append(current); current = char
            else: current = candidate
        if current: lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y

def rounded(draw, rect, fill, outline=None, radius=24, width=2):
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=width)

def arrow(draw, a, b, fill, label=""):
    ax, ay = a; bx, by = b
    midx = (ax + bx) // 2
    draw.line([(ax, ay), (midx, ay), (midx, by), (bx, by)], fill=fill, width=4)
    draw.polygon([(bx, by), (bx - 15, by - 8), (bx - 15, by + 8)], fill=fill)
    if label and label not in {"source", "default"}:
        draw.rounded_rectangle((midx - 8, min(ay, by) + 4, midx + 8 + len(label)*16, min(ay, by)+34), radius=8, fill="#fff7d6")
        draw.text((midx, min(ay, by)+7), label, font=font(16), fill="#795400")

def render_section(key, title, subtitle, ids, nodes, edges):
    cols = 3 if len(ids) > 5 else 2
    rows = (len(ids) + cols - 1) // cols
    cw, ch, gap, margin = 820, 250, 70, 80
    header = 180
    width = margin * 2 + cols * cw + (cols - 1) * gap
    height = header + rows * ch + (rows - 1) * gap + margin
    im = Image.new("RGB", (width, height), "#f7f9fc")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, width, header), fill="#0d2547")
    d.text((margin, 42), title, font=font(42), fill="white")
    d.text((margin, 102), subtitle, font=font(24), fill="#c9d9ec")
    pos = {}
    for index, node_id in enumerate(ids):
        row, col = divmod(index, cols)
        x = margin + col * (cw + gap); y = header + row * (ch + gap)
        pos[node_id] = (x, y, x+cw, y+ch)
    # Draw edges first so connection lines never cover node text.
    for e in edges:
        src, tgt = e["source"], e["target"]
        label = e.get("sourceHandle") or ""
        if src in pos and tgt in pos:
            sx1, sy1, sx2, sy2 = pos[src]
            tx1, ty1, tx2, ty2 = pos[tgt]
            if sy1 == ty1:
                right = tx1 > sx1
                a = (sx2 if right else sx1, (sy1+sy2)//2)
                b = (tx1 if right else tx2, (ty1+ty2)//2)
                points = [a,b]
            else:
                # Route through card gutters, then enter the target vertically.
                lower = ty1 > sy1
                a = (sx2,(sy1+sy2)//2)
                gutter_x = sx2 + 22
                gutter_y = ty1-30 if lower else ty2+30
                b = ((tx1+tx2)//2,ty1 if lower else ty2)
                points = [a,(gutter_x,a[1]),(gutter_x,gutter_y),(b[0],gutter_y),b]
            d.line(points, fill="#7591ae", width=4)
            import math
            dx,dy=b[0]-points[-2][0],b[1]-points[-2][1]
            size=max(1,math.hypot(dx,dy)); ux,uy=dx/size,dy/size
            d.polygon([b,(b[0]-15*ux+8*uy,b[1]-15*uy-8*ux),(b[0]-15*ux-8*uy,b[1]-15*uy+8*ux)],fill="#7591ae")
            if label and label not in {"source","default"}:
                lx,ly=points[1]
                ly+=6
                label_width=d.textlength(label,font=font(15))+16
                d.rounded_rectangle((lx,ly,lx+label_width,ly+25),radius=6,fill="#fff3ce")
                d.text((lx+8,ly+3),label,font=font(15),fill="#775200")
        elif src in pos or tgt in pos:
            node_id = src if src in pos else tgt
            x1,y1,x2,y2 = pos[node_id]
            entering = tgt in pos
            txt = ("入口：" + src) if entering else ("出口：" + tgt)
            y = y1+ch-26 if entering else y1+ch-50
            d.rounded_rectangle((x1+18, y, min(x2-18, x1+18+len(txt)*17), y+24), radius=8, fill="#fff3ce")
            d.text((x1+26,y+3), txt, font=font(15), fill="#775200")
    for node_id in ids:
        x, y, x2, y2 = pos[node_id]
        rounded(d, (x, y, x2, y2), "white", "#bdd0e4", 24, 3)
        nd = nodes[node_id]["data"]
        tp = nd.get("type", "")
        d.rectangle((x, y, x2, y+52), fill="#e7f0fa")
        d.text((x+22, y+12), nd.get("title") or "循环起点", font=font(27), fill="#102d52")
        type_text = TYPE_CN.get(tp, tp)
        tw = d.textlength(type_text, font=font(18))
        d.rounded_rectangle((x2-tw-48, y+12, x2-18, y+40), radius=12, fill="#ccdef2")
        d.text((x2-tw-33, y+16), type_text, font=font(18), fill="#274f7d")
        purpose, input_text, output_text = SHORT.get(node_id, (nd.get("desc") or "处理流程数据", "见节点配置", "见节点配置"))
        d.text((x+22, y+68), f"ID  {node_id}", font=font(17), fill="#607080")
        draw_text(d, (x+22, y+98), purpose, font(23), "#172536", cw-44, 5)
        d.text((x+22, y+158), f"入  {input_text}", font=font(18), fill="#455567")
        d.text((x+22, y+193), f"出  {output_text}", font=font(18), fill="#455567")
    # Repaint cross-stage markers on top of cards; these are labels, not invented edges.
    for e in edges:
        src, tgt = e["source"], e["target"]
        if (src in pos) == (tgt in pos):
            continue
        node_id = src if src in pos else tgt
        x1, y1, x2, y2 = pos[node_id]
        txt = ("入口：" + src) if tgt in pos else ("出口：" + tgt)
        y = y2 - 30 if tgt in pos else y2 - 56
        d.rounded_rectangle((x1+18, y, min(x2-18, x1+18+len(txt)*17), y+24), radius=8, fill="#fff3ce")
        d.text((x1+26,y+3), txt, font=font(15), fill="#775200")
    im.save(ROOT / f"{key}.png", optimize=True)

def render_overview(nodes, edges):
    width, height = 2700, 1160
    im = Image.new("RGB", (width, height), "#f7f9fc")
    d = ImageDraw.Draw(im)
    d.rectangle((0,0,width,180),fill="#0d2547")
    d.text((80,42), "本地知识库问答｜学习导航", font=font(46), fill="white")
    d.text((80,108), "六张分段图展示实际边；完整变量、代码与提示词请对照节点参考。", font=font(24), fill="#c9d9ec")
    boxes=[]
    for i,(key,title,subtitle,ids) in enumerate(SECTIONS):
        row,col=divmod(i,3)
        x=80+col*850; y=250+row*390
        box=(x,y,x+750,y+290); boxes.append(box)
        rounded(d,box,"white","#bdd0e4",28,3)
        d.text((x+32,y+32),title,font=font(34),fill="#102d52")
        draw_text(d,(x+32,y+94),subtitle,font(23),"#3e5268",680,6)
        d.text((x+32,y+218),f"{len(ids)} 个节点 · 见 workflow/{key}.png",font=font(19),fill="#607080")
    d.rounded_rectangle((80, 925, 2620, 1000), radius=20, fill="#e7f0fa")
    d.text((112, 944), "主线：01 附件上下文  →  02 检索计划  →  03 文字检索  →  04 证据校验  →  05 原图补充  →  06 引用输出", font=font(24), fill="#234d7b")
    d.text((80,1050), "分支终点：02 需要澄清时直接回复；03 检索服务失败时说明异常。图示依据 local_knowledge_chatflow.yml 重绘，总节点数 40。",font=font(22),fill="#4b5f73")
    im.save(ROOT / "workflow-overview.png", optimize=True)

def redacted(value):
    """公开占位符保留，任何疑似实际密钥一律隐藏。"""
    if isinstance(value, dict): return {k:redacted(v) for k,v in value.items()}
    if isinstance(value, list): return [redacted(v) for v in value]
    if isinstance(value, str):
        return re.sub(r'(?i)(api[_-]?key|token|secret)([=:]\s*)(?!\{\{#env\.)[^\s\'\"]+', r'\1\2[REDACTED]', value)
    return value

def inputs_for(d):
    items=[]
    for var in d.get("variables", []) or []:
        if isinstance(var, dict): items.append(f"`{var.get('variable', '未命名')}` ← `{selector(var.get('value_selector', []))}`")
    if d.get("variable_selector"):
        items.append(f"文件/上下文 ← `{selector(d['variable_selector'])}`")
    if d.get("iterator_selector"):
        items.append(f"迭代输入 ← `{selector(d['iterator_selector'])}`")
    if d.get("prompt_template"):
        refs=sorted(set(re.findall(r'\{\{#([^#]+)#\}\}', yaml_text(d['prompt_template']))))
        if refs: items.append("提示词变量 ← " + "、".join(f"`{x}`" for x in refs))
    return items or ["此节点没有在 DSL 的 `variables` 中声明显式输入。"]

def node_reference(graph):
    lines=[
        "# 完整节点参考", "",
        "这份文档逐项展开公开 DSL 的 40 个节点。所有变量选择器、条件、代码、提示词和模型配置均来自 `local_knowledge_chatflow.yml`。HTTP 节点只保留环境变量占位符；没有公开任何实际密钥。", "",
        "## 快速索引", "",
    ]
    for key,title,_,ids in SECTIONS:
        links=" · ".join(f"[{graph['nodes'][x]['data'].get('title') or x}](#node-{x})" for x in ids)
        lines += [f"- [{title}](#{key})：{links}"]
    for key,title,subtitle,ids in SECTIONS:
        lines += ["", f"## {title}", f"<a id=\"{key}\"></a>", "", subtitle, ""]
        for node_id in ids:
            node=graph['nodes'][node_id]; d=node['data']; tp=d.get('type','')
            lines += [f"### {d.get('title') or '迭代开始'}", f"<a id=\"node-{node_id}\"></a>", "",
                      f"- **ID**：`{node_id}`", f"- **类型**：`{tp}`（{TYPE_CN.get(tp,tp)}）",
                      f"- **用途**：{d.get('desc') or '流程控制节点。'}", "", "**真实输入**", ""]
            lines += [f"- {x}" for x in inputs_for(d)]
            outputs=d.get('outputs') or {}
            if d.get('output_selector'): outputs={"iteration_output": {"selector":d['output_selector'],"type":d.get('output_type')}}
            lines += ["", "**真实输出**", ""]
            if outputs:
                lines += [f"- `{name}`：`{(spec or {}).get('type','未声明')}`" for name,spec in outputs.items()]
            elif tp == 'llm': lines.append("- `text`：模型文本输出（下游以 `节点ID.text` 引用）。")
            elif tp == 'http-request': lines.append("- `status_code`、`body` 等 HTTP 响应字段（下游选择器以 DSL 为准）。")
            elif tp == 'variable-aggregator': lines.append("- `output`：从配置变量中选择的合并结果。")
            elif tp == 'document-extractor': lines.append("- `text`：提取的文档文字。")
            elif tp == 'answer': lines.append("- Dify 的最终回复。")
            else: lines.append("- 此控制节点不声明业务输出。")
            if d.get('cases'):
                lines += ["", "**条件**", "", "```yaml", yaml_text(d['cases']), "```"]
            if d.get('model'):
                lines += ["", "**模型配置**", "", "```yaml", yaml_text(d['model']), "```"]
            if d.get('prompt_template'):
                lines += ["", "<details><summary>完整提示词</summary>", ""]
                for prompt in d['prompt_template']:
                    lines += [f"**{prompt.get('role','user')}**", "", "```text", prompt.get('text',''), "```"]
                lines += ["", "</details>"]
            if d.get('code'):
                lines += ["", "<details><summary>完整 Python 代码</summary>", "", "```python", d['code'].rstrip(), "```", "", "</details>"]
            remainder=redacted(copy.deepcopy(d))
            for k in ('code','prompt_template','model','cases','variables','outputs'):
                remainder.pop(k,None)
            lines += ["", "<details><summary>其余 DSL 配置</summary>", "", "```yaml", yaml_text(remainder), "```", "", "</details>", ""]
    return "\n".join(lines).rstrip()+"\n"

def learning_doc(graph):
    return """# 分段学习指南

这套流程的重点不是“检索后让模型自由回答”，而是把问题理解、检索、证据核验、图片解读和引用输出拆开。学习时先沿着主线看，再回到每个节点的配置；六张图用短标签方便读结构，完整变量、代码和提示词都收在[节点参考](NODE_REFERENCE.md)。

## 先看全局

![六阶段导航](workflow-overview.png)

主线是：本轮附件 → 检索计划 → bridge 检索 → 候选证据核验 → 可选的关联原图解读 → 带引用的回答。图由 DSL 重绘，展示的是实际连线和分支，不是 Dify 截图。

## 1. 附件只服务这一轮

![附件处理](section-01.png)

有附件时，流程串行读取 `sys.files`：图片由视觉模型只记录可见事实，文档由提取器读取正文。两种结果被统一封装并合并；没有附件时走空上下文分支。这里的附件不会被送入 `/ingest`，也不会写入 Qdrant。循环内读取失败的策略是终止本轮，因此排查时先看附件是否可读。

## 2. 形成并校验检索计划

![检索计划](section-02.png)

模型先输出结构化 JSON：检索问题、已确认事实、是否需要澄清和一句澄清问题。`query_guard` 再做代码级校验。只有主题或意图无法确定时，`clarification_gate` 才会直接回复追问；其它情况进入检索。因此“原因未知”本身不是阻止检索的条件。

## 3. 检索和故障分支

![检索与服务故障](section-03.png)

`build_knowledge_request` 发送给 bridge 的 `knowledge_id` 是固定字符串 `local_all`，它是 bridge 的知识空间参数，不是 Dify 的外部知识集选择器。请求的 `top_k` 是 5，`score_threshold` 是 0。HTTP 不是 200、JSON 格式不对或 records 不合法时，`knowledge_retrieval` 会把 `retrieval_ok` 设为 false，随后走“检索服务异常”回复；这与“检索正常但没有足够证据”不同。成功时才把最多 10 条返回记录编号为候选。

## 4. 先筛选，再验证逐字摘录

![证据筛选与校验](section-04.png)

证据模型不能直接决定回答。它只能提交候选 ID 和连续逐字摘录；`validate_evidence_filter` 会检查摘录是否真的出现在对应候选中，再附加由检索记录提供的来源映射。校验不通过的条目会被丢弃，后面回答模型只能看到通过的证据。

## 5. 关联原图是可选补充

![关联原图解读](section-05.png)

只有已校验的 query 会用于关联图请求，`top_k` 同样是 5。HTTP 返回已到达解析节点时，查图异常可转成 notice，继续文字回答；但 `related_images` 没有配置 HTTP 节点失败默认值，因此连接失败或超时仍可能直接中断运行，不能把所有查图失败都理解为可自动降级。每张原图都要先下载并通过状态检查；下载失败会标记失败，成功才交给视觉模型。最终图片观察被汇总给回答模型，但不能替代文字证据的引用校验。

## 6. 回答必须经过引用检查

![回答与引用输出](section-06.png)

回答模型按约定输出答案和使用的证据 ID。`format_grounded_answer` 会拒绝未验证的引用、空引用和不合格式的回答，并在成功时整理资料链接。最终 `answer` 节点按顺序拼接 `format_grounded_answer.answer_text`、`format_image_results.markdown`、`format_grounded_answer.sources_markdown`，也就是正文、图片补充和文档来源。

## 阅读顺序与运行前提

1. 先看上面的六张图，理解每段输入、输出和分支。
2. 在[节点参考](NODE_REFERENCE.md)中打开同 ID 的节点，阅读代码、完整提示词和模型配置。
3. 最后查看[导入说明](IMPORT.md)并导入 DSL。

当前公开文件中的模型配置都是 `provider: langgenius/deepseek/deepseek`、`name: deepseek-flash`。DSL 的 `dependencies` 为空，目标 Dify 环境需要自行安装对应插件并重新绑定模型；视觉节点还要确认模型支持图片。公开 DSL 未包含有效密钥，且尚未在另一套环境完成导入运行验证。
"""

def readme():
    return """# 本地知识库问答：让资料真的派上用场

资料散在笔记、文档和截图里时，难的往往不是“问 AI”，而是弄清它凭什么这么回答。

这是一个在 Dify 中逐步打磨的本地知识库 Chatflow：先理解问题并检索资料，再让回答只引用能核对的证据。本轮上传的附件也能参与理解，但不会被这个流程送去入库。它适合作为搭建本地 RAG 的学习起点；bridge、向量库和模型仍需要你自己的环境。

## 先从流程总览开始

![六阶段流程导航](workflow/workflow-overview.png)

这张图和后面的分段图都由公开 DSL 重绘，便于阅读结构与实际分支；它们不是 Dify 画布截图。完整配置请继续往下读。

## 分段学习

[分段学习指南](workflow/LEARNING.md)按附件、检索计划、检索与故障、证据校验、关联原图、回答输出六段解释机制与失败分支，并嵌入六张可放大的中文流程图。

| 阶段 | 图 | 学习重点 |
| --- | --- | --- |
| 01 | [本轮附件](workflow/section-01.png) | 图片/文档分流与临时上下文 |
| 02 | [检索计划](workflow/section-02.png) | JSON 计划、校验与澄清分支 |
| 03 | [检索与故障](workflow/section-03.png) | bridge 请求与服务异常区分 |
| 04 | [证据筛选与校验](workflow/section-04.png) | 连续原文摘录和代码验证 |
| 05 | [关联原图解读](workflow/section-05.png) | 下载校验和视觉补充 |
| 06 | [答案与引用输出](workflow/section-06.png) | 已验证引用的最终把关 |

## 节点参考

[完整节点参考](workflow/NODE_REFERENCE.md)覆盖全部 40 个节点：真实变量选择器、输出、条件、模型配置、完整提示词、全部 Python 代码和其余 DSL 配置均可按节点 ID 对照。

## 导入与配置

[导入说明](workflow/IMPORT.md)说明模型插件、bridge 地址、密钥和本轮附件行为。公开 DSL 中不含有效密钥；请只在自己的 Dify 环境变量中填写 `BRIDGE_API_KEY`。

## DSL

[下载 Dify Chatflow DSL](workflow/local_knowledge_chatflow.yml)。该文件的工作流图来自当前发布图快照，其余应用导入配置沿用本地 DSL 底稿。它尚未在另一套 Dify 环境完成导入和运行验证，导入后请自行绑定模型、知识资源和 bridge 后测试。
"""

def main():
    app=yaml.safe_load(DSL.read_text())
    graph=app['workflow']['graph']
    graph['nodes']={n['id']:n for n in graph['nodes']}
    for key,title,subtitle,ids in SECTIONS:
        render_section(key,title,subtitle,ids,graph['nodes'],graph['edges'])
    render_overview(graph['nodes'],graph['edges'])
    (ROOT/'NODE_REFERENCE.md').write_text(node_reference(graph))
    (ROOT/'LEARNING.md').write_text(learning_doc(graph))
    (ROOT.parent/'README.md').write_text(readme())

if __name__ == '__main__':
    main()
