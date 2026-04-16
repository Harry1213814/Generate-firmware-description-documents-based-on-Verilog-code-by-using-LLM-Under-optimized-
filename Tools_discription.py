rd_verilog_description = """
读取 Verilog/SystemVerilog 源码文件。

函数签名：
rd_verilog(file_path: str, start: int = None, end: int = None) -> dict

参数说明：
- file_path: 要读取的 .v 或 .sv 文件路径，字符串类型。
- start: 起始行号，可选，从 1 开始计数。若为 None，则默认从文件开头读取。
- end: 结束行号，可选，从 1 开始计数。若为 None，则默认读到文件末尾。

功能说明：
- 当 start 和 end 都为 None 时，返回整个文件的源码。
- 当提供 start 和 end 时，返回指定行范围内的源码。
- 适合在分析 Verilog 文件、提取局部代码、生成文档引用代码时使用。

返回结果：
返回一个字典，格式如下：
{
    "filename": 文件名,
    "filepath": 文件绝对路径,
    "source_code": 读取到的源码字符串,
    "line_count": 文件总行数,
    "read_ok": 是否读取成功,
    "error": 错误信息
}

调用示例：
rd_verilog(file_path="rtl/uart_rx.v", start=None, end=None)
rd_verilog(file_path="rtl/uart_rx.v", start=10, end=40)
"""

wr_json_description = """
对 Verilog 摘要 JSON 数据库进行增、改、查、列举操作。

函数签名：
wr_json(operation: str, json_db_path: str, payload: dict) -> dict

参数说明：
- operation: 操作类型，支持 "add"、"update"、"updata"、"query"、"list"。
- json_db_path: 摘要 JSON 文件路径。
- payload: 与具体操作对应的输入内容，必须是字典。

功能说明：
1. add
   在 JSON 数据库末尾追加一个新的 Verilog 文件条目。
   payload 格式：
   {
       "file_entry": {
           "filename": "xxx.v",
           "filepath": "/abs/path/xxx.v",
           "code_function_descriptions": [...],
           "code_indices": [...],
           "reflection_feedback": [...]
       }
   }

2. update / updata
   更新某个已存在文件的一个指定块。
   一次只能更新一个块。
   block_name 只能是以下三者之一：
   - "code_function_descriptions"
   - "code_indices"
   - "reflection_feedback"

   payload 格式：
   {
       "file_name": "xxx.v",
       "block_name": "code_function_descriptions",
       "new_content": [...]
   }

3. query
   查询某个文件对应的完整 JSON 片段。
   payload 格式：
   {
       "file_name": "xxx.v"
   }

4. list
   列出当前 JSON 数据库中已经处理过的文件。
   payload 格式：
   {}

返回结果：
返回一个字典，通常包含：
{
    "success": 是否成功,
    "message": 状态说明,
    "data": 返回数据
}

补充说明：
- add 时系统会自动为每个 .v 文件分配 file_id，例如 F00、F01、...、F24。
- 该工具适合在 Plan-and-Solve 阶段写入代码摘要，也适合在 Reflection 阶段写入反馈。

调用示例：
wr_json(
    operation="add",
    json_db_path="verilog_summary.json",
    payload={
        "file_entry": {
            "filename": "uart_rx.v",
            "filepath": "/abs/path/uart_rx.v",
            "code_function_descriptions": [],
            "code_indices": [],
            "reflection_feedback": []
        }
    }
)

wr_json(
    operation="update",
    json_db_path="verilog_summary.json",
    payload={
        "file_name": "uart_rx.v",
        "block_name": "reflection_feedback",
        "new_content": [{"round": 1, "comment": "描述不完整"}]
    }
)

wr_json(
    operation="query",
    json_db_path="verilog_summary.json",
    payload={"file_name": "uart_rx.v"}
)

wr_json(
    operation="list",
    json_db_path="verilog_summary.json",
    payload={}
)
"""

wr_doc_json_description = """
对固件说明文档的 JSON 映射版本进行增、改、删、查、列举操作。

函数签名：
wr_doc_json(operation: str, doc_json_path: str, payload: dict) -> dict

参数说明：
- operation: 操作类型，支持 "set_meta"、"add"、"update"、"updata"、"delete"、"query"、"list"。
- doc_json_path: 文档 JSON 映射文件路径。
- payload: 与具体操作对应的输入内容，必须是字典。

功能说明：
该工具用于维护 docx 文档的 JSON 映射版本，让大模型能够以“小节”为粒度对文档进行局部编辑，而不必每次全文重写。
它适合作为正式 docx 文档生成之前的中间编辑层，支持按 section_number（如 "1.1"）或 section_title（如 "时基初始化"）定位目标小节。
通过该工具，大模型可以逐小节新增、修改、删除和查询内容，从而显著减少 DOC 重写阶段的 Token 消耗。

DOC JSON 的根结构通常包含：
- doc_name: 目标 docx 文件名
- doc_path: 目标 docx 文件路径
- doc_title: 文档标题
- sections: 小节列表

每个 sections 中的小节条目通常包含：
- section_id: 小节唯一标识符，例如 S001、S002
- section_number: 小节编号，例如 "1.1"
- section_title: 小节标题，例如 "时基初始化"
- heading_level: 标题层级，通常对应 docx 中的 Heading 级别
- content: 小节正文内容列表
- source_refs: 与该小节对应的源码引用信息
- tags: 小节标签列表

其中 content 一般是一个列表，元素可以是如下结构：
{
    "block_id": "B001",
    "block_type": "paragraph" 或 "code" 或 "bullet" 或 "table_note",
    "text": "正文或代码文本",
    "language": "c"    # 仅 code 类型可选
}

支持的操作如下：

1. set_meta
   设置或更新文档元信息。
   可用于在开始写文档前初始化 doc_name、doc_path 和 doc_title。

   payload 格式：
   {
       "doc_name": ".statement.docx",
       "doc_path": "/abs/path/.statement.docx",
       "doc_title": "固件说明文档"
   }

2. add
   新增一个文档小节。
   默认追加到文末；如果提供 insert_after，则插入到指定小节之后。
   小节索引主要依靠 section_number 或 section_title。

   payload 格式：
   {
       "section_entry": {
           "section_number": "1.1",
           "section_title": "时基初始化",
           "heading_level": 2,
           "content": [
               {
                   "block_type": "paragraph",
                   "text": "为什么需要这个功能……"
               },
               {
                   "block_type": "code",
                   "language": "c",
                   "text": "void Stm32_Clock_Init(u8 PLL) { ... }"
               },
               {
                   "block_type": "paragraph",
                   "text": "解释这段代码如何实现该功能……"
               }
           ],
           "source_refs": [
               {
                   "file_name": "clock.v",
                   "file_path": "/abs/path/clock.v",
                   "line_start": 1,
                   "line_end": 25
               }
           ],
           "tags": ["初始化", "时钟"]
       },

       "insert_after": {
           "section_number": "1.0"
       }
   }

   说明：
   - insert_after 为可选字段。
   - 若不提供 insert_after，则小节会直接追加到 sections 末尾。
   - 系统会自动分配 section_id，例如 S001、S002。

3. update / updata
   更新某个已存在小节的一个指定块。
   一次只能更新一个块。

   block_name 只能是以下之一：
   - "section_number"
   - "section_title"
   - "heading_level"
   - "content"
   - "source_refs"
   - "tags"

   payload 格式：
   {
       "section_number": "1.1",
       "block_name": "content",
       "new_content": [
           {
               "block_type": "paragraph",
               "text": "新的功能说明……"
           },
           {
               "block_type": "code",
               "language": "c",
               "text": "void xxx() { ... }"
           },
           {
               "block_type": "paragraph",
               "text": "新的代码解释……"
           }
       ]
   }

   说明：
   - section_number 和 section_title 至少提供一个，用于定位小节。
   - 若同时提供两者，则会更精确地定位目标小节。
   - 当 block_name 为 content 时，new_content 必须是列表。
   - 当 block_name 为 heading_level 时，new_content 必须是正整数。
   - 当 block_name 为 section_number 或 section_title 时，new_content 必须是字符串。

4. delete
   删除某个文档小节。

   payload 格式：
   {
       "section_number": "1.1"
   }

   或：
   {
       "section_title": "时基初始化"
   }

   说明：
   - section_number 和 section_title 至少提供一个。
   - 删除后，该小节会从 sections 列表中移除。

5. query
   查询整个 DOC JSON，或查询某个指定小节。

   查询整个文档：
   payload 格式：
   {}

   查询某个小节：
   payload 格式：
   {
       "section_number": "1.1"
   }

   或：
   {
       "section_title": "时基初始化"
   }

   说明：
   - 当 payload 中不提供 section_number 和 section_title 时，返回整个文档 JSON。
   - 当提供 section_number 或 section_title 时，返回对应小节的完整 JSON 片段。

6. list
   列出当前文档中所有小节的目录信息。

   payload 格式：
   {}

   返回内容通常包括：
   - 小节顺序
   - section_id
   - section_number
   - section_title
   - heading_level
   - content_block_count

返回结果：
返回一个字典，通常包含：
{
    "success": 是否成功,
    "message": 状态说明,
    "data": 返回数据
}

适用场景：
- 在 DOC 初次生成阶段，先建立文档 JSON 映射，而不是直接写整篇 docx
- 在 DOC 反馈阶段，只查询或修改某个功能小节
- 在 DOC 重写阶段，按小节增改删内容，而不必全文推倒重来
- 在最终落盘前，先通过 JSON 结构稳定文档逻辑和章节组织

调用示例：
wr_doc_json(
    operation="set_meta",
    doc_json_path=".statement_doc.json",
    payload={
        "doc_name": ".statement.docx",
        "doc_path": ".statement.docx",
        "doc_title": "固件说明文档"
    }
)

wr_doc_json(
    operation="add",
    doc_json_path=".statement_doc.json",
    payload={
        "section_entry": {
            "section_number": "1.1",
            "section_title": "时基初始化",
            "heading_level": 2,
            "content": [
                {
                    "block_type": "paragraph",
                    "text": "系统启动后需要首先建立统一时基，否则后续延时和定时功能无法可靠运行。"
                },
                {
                    "block_type": "code",
                    "language": "c",
                    "text": "void Stm32_Clock_Init(u8 PLL) { ... }"
                },
                {
                    "block_type": "paragraph",
                    "text": "该函数通过配置系统时钟和 SysTick，为后续程序提供统一的微秒和毫秒时间基准。"
                }
            ],
            "source_refs": [
                {
                    "file_name": "clock.v",
                    "file_path": "/abs/path/clock.v",
                    "line_start": 1,
                    "line_end": 25
                }
            ],
            "tags": ["初始化", "时钟"]
        }
    }
)

wr_doc_json(
    operation="update",
    doc_json_path=".statement_doc.json",
    payload={
        "section_number": "1.1",
        "block_name": "content",
        "new_content": [
            {
                "block_type": "paragraph",
                "text": "新的功能说明……"
            },
            {
                "block_type": "code",
                "language": "c",
                "text": "void xxx() { ... }"
            },
            {
                "block_type": "paragraph",
                "text": "新的代码实现解释……"
            }
        ]
    }
)

wr_doc_json(
    operation="query",
    doc_json_path=".statement_doc.json",
    payload={
        "section_title": "时基初始化"
    }
)

wr_doc_json(
    operation="list",
    doc_json_path=".statement_doc.json",
    payload={}
)

wr_doc_json(
    operation="delete",
    doc_json_path=".statement_doc.json",
    payload={
        "section_number": "1.1"
    }
)
"""

wr_doc_feedback_json_description = """
对 DOC 反馈 JSON 数据库进行增、改、查、列举操作。

函数签名：
wr_doc_feedback_json(operation: str, doc_feedback_json_path: str, payload: dict) -> dict

参数说明：
- operation: 操作类型，支持 "add"、"update"、"updata"、"query"、"list"。
- doc_feedback_json_path: DOC 反馈 JSON 文件路径。
- payload: 与具体操作对应的输入内容，必须是字典。

功能说明：
该工具用于保存和管理对已生成固件描述文档的质量反馈，不用于保存 Verilog 文件摘要。它维护的是一个独立的 DOC 反馈数据库，每个条目对应一个 docx 文档，并记录该文档当前存在的问题和下一版推荐的重写结构。

每个 DOC 反馈条目通常包含以下字段：
- doc_name: 文档文件名，通常为 .docx 文件
- doc_path: 文档路径
- overall_assessment: 对当前文档整体质量的总体评价
- must_fix: 必须修正的问题列表
- should_fix: 建议优化的问题列表
- forbidden_content_found: 当前文档中出现但不应保留的内容
- section_feedback: 按小节或按问题类型给出的具体反馈
- recommended_structure: 下一版 DOC 应采用的推荐结构

支持的操作如下：

1. add
   新增一个 DOC 反馈条目。
   payload 格式：
   {
       "feedback_entry": {
           "doc_name": ".statement.docx",
           "doc_path": "/abs/path/.statement.docx",
           "overall_assessment": "整体评价文本",
           "must_fix": [...],
           "should_fix": [...],
           "forbidden_content_found": [...],
           "section_feedback": [...],
           "recommended_structure": [...]
       }
   }

2. update / updata
   更新某个已有 DOC 反馈条目的一个指定块。
   block_name 只能是以下之一：
   - "overall_assessment"
   - "must_fix"
   - "should_fix"
   - "forbidden_content_found"
   - "section_feedback"
   - "recommended_structure"

   payload 格式：
   {
       "doc_name": ".statement.docx",
       "block_name": "must_fix",
       "new_content": [...]
   }

3. query
   查询某个 docx 文件对应的完整反馈条目。
   payload 格式：
   {
       "doc_name": ".statement.docx"
   }

4. list
   列出当前 DOC 反馈数据库中已有的反馈条目。
   payload 格式：
   {}

返回结果：
返回一个字典，通常包含：
{
    "success": 是否成功,
    "message": 状态说明,
    "data": 返回数据
}

适用场景：
- 在 DOC 反馈阶段，将大模型对当前文档不足的评价写入 JSON 文件
- 在 DOC 重写阶段，读取上一版 DOC 的反馈内容，指导新一轮文档生成

调用示例：
wr_doc_feedback_json(
    operation="add",
    doc_feedback_json_path=".doc_feedback.json",
    payload={
        "feedback_entry": {
            "doc_name": ".statement.docx",
            "doc_path": ".statement.docx",
            "overall_assessment": "当前文档整体偏摘要化，功能单元表达不够清晰。",
            "must_fix": ["必须删去修订痕迹"],
            "should_fix": ["建议增强小节结构"],
            "forbidden_content_found": ["设计验证与反射反馈"],
            "section_feedback": [
                {
                    "section_title": "clock.v",
                    "problem": "仍然偏概述式写法",
                    "suggestion": "改为功能单元 + 代码 + 解释代码实现方式"
                }
            ],
            "recommended_structure": [
                "1. 文件A",
                "1.1 功能单元A",
                "1.1.1 为什么需要该功能",
                "1.1.2 对应代码",
                "1.1.3 代码实现说明"
            ]
        }
    }
)
"""

doc_json_to_docx_description = """
将固件说明文档的 JSON 映射版本转换为正式的 docx 文档。

函数签名：
doc_json_to_docx(doc_json_path: str, output_doc_path: str = None) -> dict

参数说明：
- doc_json_path: 由 wr_doc_json 维护的文档 JSON 映射文件路径。
- output_doc_path: 输出的 docx 文件路径，可选。若为 None，则优先使用 JSON 中记录的 doc_path；若 JSON 中未提供 doc_path，则默认生成与 JSON 同名的 .docx 文件。

功能说明：
该函数用于将 wr_doc_json 维护的中间文档结构最终落盘为 docx 文件。
它本身不负责复杂的文档编辑逻辑，而是负责把已经整理好的 JSON 小节结构按顺序转换为正式文档。
这意味着，大模型在中间阶段可以反复使用 wr_doc_json 进行局部编辑，等文档结构稳定后，再统一调用该函数生成最终 docx，从而避免在编辑阶段频繁重写整篇文档。

该函数默认会：
1. 读取 doc_json_path 对应的 JSON 文件；
2. 检查 JSON 根结构是否合法；
3. 若存在 doc_title，则将其写为文档主标题；
4. 依次遍历 sections 列表；
5. 对每个小节：
   - 根据 section_number 和 section_title 生成标题行；
   - 根据 heading_level 设置对应的标题层级；
   - 遍历 content 中的各个 block；
   - 将 paragraph / bullet / code / table_note 等块转换为对应的 docx 段落；
6. 最终保存为 .docx 文件。

输入 JSON 一般应满足如下结构：
{
    "doc_name": ".statement.docx",
    "doc_path": "/abs/path/.statement.docx",
    "doc_title": "固件说明文档",
    "sections": [
        {
            "section_id": "S001",
            "section_number": "1.1",
            "section_title": "时基初始化",
            "heading_level": 2,
            "content": [
                {
                    "block_id": "B001",
                    "block_type": "paragraph",
                    "text": "为什么需要这个功能……"
                },
                {
                    "block_id": "B002",
                    "block_type": "code",
                    "language": "c",
                    "text": "void xxx() { ... }"
                },
                {
                    "block_id": "B003",
                    "block_type": "paragraph",
                    "text": "解释代码实现方式……"
                }
            ]
        }
    ]
}

返回结果：
返回一个字典，通常包含：
{
    "success": 是否成功,
    "message": 状态说明,
    "data": {
        "doc_json_path": JSON 文件路径,
        "output_doc_path": 输出的 docx 路径,
        "section_count": 小节数量
    }
}

适用场景：
- 在所有小节已经通过 wr_doc_json 编辑完成后，统一生成正式 docx
- 在 DOC 多轮反馈和重写结束后，将最终 JSON 成稿落盘
- 作为 DOC 生成流程的最后一步，将“中间结构表示”转换为“可交付文档”

补充说明：
- 该函数不负责判断文档内容是否合理，只负责将已有 JSON 结构写入 docx。
- 若 JSON 中 sections 顺序已经排好，则生成的 docx 会按相同顺序输出。
- 若 output_doc_path 为 None，则会优先读取 JSON 中的 doc_path 字段作为输出路径。
- 若 JSON 中没有 doc_path，则默认输出为与 JSON 同路径、同名但后缀为 .docx 的文件。

调用示例：
doc_json_to_docx(
    doc_json_path=".statement_doc.json",
    output_doc_path=".statement.docx"
)

doc_json_to_docx(
    doc_json_path=".statement_doc.json"
)
"""