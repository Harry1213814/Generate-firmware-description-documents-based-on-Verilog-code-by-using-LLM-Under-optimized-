from LLM_class import HelloAgentsLLM
from Reflection_Framework_multi_toolbox import IterativeFirmwareDocAgent, WorkflowPromptSet, WorkflowToolboxSet
from Tools import (
        rd_verilog,
        wr_json,
        wr_doc_json,
        doc_json_to_docx,
        wr_doc_feedback_json,
        ToolExecutor,
    )
from plan_solve_rate_limited import LLMRateLimiter
from Tools_discription import (
        rd_verilog_description,
        wr_json_description,
        wr_doc_json_description,
        doc_json_to_docx_description,
        wr_doc_feedback_json_description,
    )
from project_files import project_files_text
from prompt_workflow_modified import (
    INIT_PLANNER_PROMPT_TEMPLATE,
    INIT_EXECUTOR_PROMPT_TEMPLATE,
    REFLECT_PLANNER_PROMPT_TEMPLATE,
    REFLECT_EXECUTOR_PROMPT_TEMPLATE,
    REVISE_PLANNER_PROMPT_TEMPLATE,
    REVISE_EXECUTOR_PROMPT_TEMPLATE,
    DOC_PLANNER_PROMPT_TEMPLATE,
    DOC_EXECUTOR_PROMPT_TEMPLATE,
    DOC_REFLECT_PLANNER_PROMPT_TEMPLATE,
    DOC_REFLECT_EXECUTOR_PROMPT_TEMPLATE,
    DOC_REVISE_PLANNER_PROMPT_TEMPLATE,
    DOC_REVISE_EXECUTOR_PROMPT_TEMPLATE,
    DOC_RENDER_PLANNER_PROMPT_TEMPLATE,
    DOC_RENDER_EXECUTOR_PROMPT_TEMPLATE,
)

def build_toolbox(
    enable_rd_verilog: bool = False,            # 读取verilog代码
    enable_wr_json: bool = False,               # 写代码的摘要Json
    enable_wr_doc_json: bool = False,           # 写doc的Json版本
    enable_wr_doc_feedback_json: bool = False,  # 写doc Json的反馈Json
    enable_doc_json_to_docx: bool = False,      # 将doc Json渲染成docx
):
    toolbox = ToolExecutor()

    if enable_rd_verilog:
        toolbox.registerTool("rd_verilog", rd_verilog_description, rd_verilog)
    if enable_wr_json:
        toolbox.registerTool("wr_json", wr_json_description, wr_json)
    if enable_wr_doc_json:
        toolbox.registerTool("wr_doc_json", wr_doc_json_description, wr_doc_json)
    if enable_wr_doc_feedback_json:
        toolbox.registerTool(
            "wr_doc_feedback_json",
            wr_doc_feedback_json_description,
            wr_doc_feedback_json,
        )
    if enable_doc_json_to_docx:
        toolbox.registerTool(
            "doc_json_to_docx",
            doc_json_to_docx_description,
            doc_json_to_docx,
        )

    return toolbox

llm_client = HelloAgentsLLM()

prompt_set = WorkflowPromptSet(
    init_planner_prompt=INIT_PLANNER_PROMPT_TEMPLATE,
    init_executor_prompt=INIT_EXECUTOR_PROMPT_TEMPLATE,

    reflect_planner_prompt=REFLECT_PLANNER_PROMPT_TEMPLATE,
    reflect_executor_prompt=REFLECT_EXECUTOR_PROMPT_TEMPLATE,

    revise_planner_prompt=REVISE_PLANNER_PROMPT_TEMPLATE,
    revise_executor_prompt=REVISE_EXECUTOR_PROMPT_TEMPLATE,

    doc_planner_prompt=DOC_PLANNER_PROMPT_TEMPLATE,
    doc_executor_prompt=DOC_EXECUTOR_PROMPT_TEMPLATE,

    doc_reflect_planner_prompt=DOC_REFLECT_PLANNER_PROMPT_TEMPLATE,
    doc_reflect_executor_prompt=DOC_REFLECT_EXECUTOR_PROMPT_TEMPLATE,

    doc_revise_planner_prompt=DOC_REVISE_PLANNER_PROMPT_TEMPLATE,
    doc_revise_executor_prompt=DOC_REVISE_EXECUTOR_PROMPT_TEMPLATE,

    doc_render_planner_prompt=DOC_RENDER_PLANNER_PROMPT_TEMPLATE,
    doc_render_executor_prompt=DOC_RENDER_EXECUTOR_PROMPT_TEMPLATE,
)

toolbox_set = WorkflowToolboxSet(
    # 摘要 JSON 阶段
    init_toolbox=build_toolbox(
        enable_rd_verilog=True,
        enable_wr_json=True,
    ),
    reflect_toolbox=build_toolbox(
        enable_rd_verilog=True,
        enable_wr_json=True,
    ),
    revise_toolbox=build_toolbox(
        enable_rd_verilog=True,
        enable_wr_json=True,
    ),

    # 第一次 DOC JSON 生成
    doc_init_toolbox=build_toolbox(
        enable_rd_verilog=True,
        enable_wr_json=True,
        enable_wr_doc_json=True,
    ),

    # DOC 反馈：读取 DOC JSON + 摘要 JSON + 源代码，并写 DOC 反馈 JSON
    doc_reflect_toolbox=build_toolbox(
        enable_rd_verilog=True,
        enable_wr_json=True,
        enable_wr_doc_json=True,
        enable_wr_doc_feedback_json=True,
    ),

    # DOC 重写：读取 / 更新 DOC JSON，并读取 DOC 反馈 JSON
    doc_revise_toolbox=build_toolbox(
        enable_rd_verilog=True,
        enable_wr_json=True,
        enable_wr_doc_json=True,
        enable_wr_doc_feedback_json=True,
    ),

    # DOC 渲染：只允许在本阶段使用 doc_json_to_docx
    doc_render_toolbox=build_toolbox(
        enable_wr_doc_json=True,
        enable_doc_json_to_docx=True,
    ),
)

rate_limiter = LLMRateLimiter(capacity=200, refill_tokens_per_minute=200)

workflow_agent = IterativeFirmwareDocAgent(
    llm_client=llm_client,
    toolbox_set=toolbox_set,
    project_files=project_files_text,
    json_db_path=".statement.json",
    doc_json_path=".statement_doc.json",
    output_doc_path=".statement.docx",
    doc_feedback_json_path=".doc_feedback.json",
    prompt_set=prompt_set,
    rate_limiter=rate_limiter,
    max_feedback_rounds=3,
    max_doc_feedback_rounds=3,
    max_step_rounds=8,
)

results = workflow_agent.run()
for item in results:
    print(item)
