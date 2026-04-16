from dataclasses import dataclass
from typing import Dict, Any, List

from LLM_class import HelloAgentsLLM
from plan_solve_rate_limited import PlanAndSolveAgent, PhaseConfig, LLMRateLimiter


@dataclass
class WorkflowPromptSet:
    """
    定义整个工程 Agent 所有阶段用到的提示词集合。
    """
    init_planner_prompt: str
    init_executor_prompt: str

    reflect_planner_prompt: str
    reflect_executor_prompt: str

    revise_planner_prompt: str
    revise_executor_prompt: str

    doc_planner_prompt: str
    doc_executor_prompt: str

    doc_reflect_planner_prompt: str
    doc_reflect_executor_prompt: str

    doc_revise_planner_prompt: str
    doc_revise_executor_prompt: str

    doc_render_planner_prompt: str
    doc_render_executor_prompt: str


@dataclass
class WorkflowToolboxSet:
    """
    为不同阶段提供不同的工具箱。
    """
    init_toolbox: Any
    reflect_toolbox: Any
    revise_toolbox: Any

    doc_init_toolbox: Any
    doc_reflect_toolbox: Any
    doc_revise_toolbox: Any
    doc_render_toolbox: Any


class IterativeFirmwareDocAgent:
    """
    总控流程：

    A. 摘要 JSON 阶段
    1. 初始化写 JSON（修改第1次）
    2. 反馈第1轮
    3. 根据反馈修改第2次
    4. 反馈第2轮
    5. 根据反馈修改第3次
    6. 反馈第3轮
    7. 根据反馈修改第4次

    B. DOC JSON 阶段
    8. 第1次 DOC JSON 生成
    9. 第1轮 DOC 反馈
    10. 第2次 DOC JSON 修改
    11. 第2轮 DOC 反馈
    12. 第3次 DOC JSON 修改
    13. 第3轮 DOC 反馈
    14. 第4次 DOC JSON 修改

    C. DOC 渲染阶段
    15. 将最终 DOC JSON 严格映射为 docx
    16. 停止
    """

    def __init__(
        self,
        llm_client,
        toolbox_set: WorkflowToolboxSet,
        project_files: str,
        json_db_path: str,
        doc_json_path: str,
        output_doc_path: str,
        doc_feedback_json_path: str,
        prompt_set: WorkflowPromptSet,
        rate_limiter: LLMRateLimiter,
        max_feedback_rounds: int = 3,
        max_doc_feedback_rounds: int = 3,
        max_step_rounds: int = 8,
    ):
        self.llm_client = llm_client
        self.toolbox_set = toolbox_set
        self.project_files = project_files
        self.json_db_path = json_db_path
        self.doc_json_path = doc_json_path
        self.output_doc_path = output_doc_path
        self.doc_feedback_json_path = doc_feedback_json_path
        self.prompt_set = prompt_set
        self.rate_limiter = rate_limiter
        self.max_feedback_rounds = max_feedback_rounds
        self.max_doc_feedback_rounds = max_doc_feedback_rounds
        self.max_step_rounds = max_step_rounds

    def _run_phase(self, phase_config: PhaseConfig, toolbox) -> Dict[str, Any]:
        agent = PlanAndSolveAgent(
            llm_client=self.llm_client,
            toolbox=toolbox,
            project_files=self.project_files,
            json_db_path=self.json_db_path,
            output_doc_path=self.output_doc_path,
            phase_config=phase_config,
            rate_limiter=self.rate_limiter,
        )
        return agent.run()

    def run(self) -> List[Dict[str, Any]]:
        all_results = []

        # =========================================================
        # A. 摘要 JSON 阶段：保持原逻辑
        # 如需启用，取消下面代码块注释。
        # =========================================================
        # init_phase = PhaseConfig(
        #     phase_name="初始化写JSON",
        #     task_goal="第一次分析全部 Verilog 文件，并将每个文件的摘要写入 state.json。",
        #     planner_prompt_template=self.prompt_set.init_planner_prompt,
        #     executor_prompt_template=self.prompt_set.init_executor_prompt,
        #     prompt_vars={
        #         "modify_round": 1,
        #         "feedback_round": 0,
        #         "max_feedback_rounds": self.max_feedback_rounds,
        #     },
        #     max_step_rounds=self.max_step_rounds,
        # )
        # all_results.append(self._run_phase(init_phase, self.toolbox_set.init_toolbox))

        # for feedback_round in range(1, self.max_feedback_rounds + 1):
        #     reflect_phase = PhaseConfig(
        #         phase_name=f"反馈第{feedback_round}轮",
        #         task_goal=f"检查当前 state.json 中的文件摘要是否准确完整，并为每个文件生成第 {feedback_round} 轮反馈。",
        #         planner_prompt_template=self.prompt_set.reflect_planner_prompt,
        #         executor_prompt_template=self.prompt_set.reflect_executor_prompt,
        #         prompt_vars={
        #             "feedback_round": feedback_round,
        #             "modify_round": feedback_round,
        #             "max_feedback_rounds": self.max_feedback_rounds,
        #         },
        #         max_step_rounds=self.max_step_rounds,
        #     )
        #     all_results.append(self._run_phase(reflect_phase, self.toolbox_set.reflect_toolbox))
        #
        #     revise_phase = PhaseConfig(
        #         phase_name=f"根据反馈修改第{feedback_round + 1}次",
        #         task_goal=f"读取 state.json 中已有摘要和第 {feedback_round} 轮反馈，修正文件摘要内容。",
        #         planner_prompt_template=self.prompt_set.revise_planner_prompt,
        #         executor_prompt_template=self.prompt_set.revise_executor_prompt,
        #         prompt_vars={
        #             "feedback_round": feedback_round,
        #             "modify_round": feedback_round + 1,
        #             "max_feedback_rounds": self.max_feedback_rounds,
        #         },
        #         max_step_rounds=self.max_step_rounds,
        #     )
        #     all_results.append(self._run_phase(revise_phase, self.toolbox_set.revise_toolbox))

        # =========================================================
        # B. DOC JSON 阶段
        # 第1次 DOC JSON 生成
        # =========================================================
        # doc_init_phase = PhaseConfig(
        #     phase_name="第一次生成DOC_JSON文档",
        #     task_goal="基于最终 state.json 中的摘要内容和源代码，第一次生成固件描述文档的 DOC JSON 映射版本。",
        #     planner_prompt_template=self.prompt_set.doc_planner_prompt,
        #     executor_prompt_template=self.prompt_set.doc_executor_prompt,
        #     prompt_vars={
        #         "feedback_round": self.max_feedback_rounds,
        #         "modify_round": self.max_feedback_rounds + 1,
        #         "max_feedback_rounds": self.max_feedback_rounds,
        #         "doc_feedback_round": 0,
        #         "doc_revise_round": 1,
        #         "doc_feedback_json_path": self.doc_feedback_json_path,
        #         "doc_json_path": self.doc_json_path,
        #     },
        #     max_step_rounds=self.max_step_rounds,
        # )
        # all_results.append(self._run_phase(doc_init_phase, self.toolbox_set.doc_init_toolbox))

        # =========================================================
        # DOC 反馈 + DOC JSON 重写：共3轮反馈，重写到第4次后停止
        # =========================================================
        for doc_feedback_round in range(1, self.max_doc_feedback_rounds + 1):
            # 1) DOC 反馈
            doc_reflect_phase = PhaseConfig(
                phase_name=f"DOC反馈第{doc_feedback_round}轮",
                task_goal=f"读取当前 DOC JSON、摘要 JSON 和源代码，检查当前固件文档内容的不足，并写入 DOC 反馈 JSON（第 {doc_feedback_round} 轮）。",
                planner_prompt_template=self.prompt_set.doc_reflect_planner_prompt,
                executor_prompt_template=self.prompt_set.doc_reflect_executor_prompt,
                prompt_vars={
                    "feedback_round": self.max_feedback_rounds,
                    "modify_round": self.max_feedback_rounds + 1,
                    "max_feedback_rounds": self.max_feedback_rounds,
                    "doc_feedback_round": doc_feedback_round,
                    "doc_revise_round": doc_feedback_round,
                    "doc_feedback_json_path": self.doc_feedback_json_path,
                    "doc_json_path": self.doc_json_path,
                },
                max_step_rounds=self.max_step_rounds,
            )
            all_results.append(self._run_phase(doc_reflect_phase, self.toolbox_set.doc_reflect_toolbox))

            # 2) 根据 DOC 反馈进行重写
            doc_revise_phase = PhaseConfig(
                phase_name=f"根据DOC反馈修改第{doc_feedback_round + 1}次DOC_JSON",
                task_goal=f"读取摘要 JSON、源代码、当前 DOC JSON 和 DOC 反馈 JSON，重写固件文档的 DOC JSON（第 {doc_feedback_round + 1} 次版本）。",
                planner_prompt_template=self.prompt_set.doc_revise_planner_prompt,
                executor_prompt_template=self.prompt_set.doc_revise_executor_prompt,
                prompt_vars={
                    "feedback_round": self.max_feedback_rounds,
                    "modify_round": self.max_feedback_rounds + 1,
                    "max_feedback_rounds": self.max_feedback_rounds,
                    "doc_feedback_round": doc_feedback_round,
                    "doc_revise_round": doc_feedback_round + 1,
                    "doc_feedback_json_path": self.doc_feedback_json_path,
                    "doc_json_path": self.doc_json_path,
                    "previous_doc_json_path": self.doc_json_path,
                },
                max_step_rounds=self.max_step_rounds,
            )
            all_results.append(self._run_phase(doc_revise_phase, self.toolbox_set.doc_revise_toolbox))

        # =========================================================
        # C. DOC JSON -> docx 渲染阶段
        # 注意：只有该阶段才允许使用 doc_json_to_docx 工具。
        # =========================================================
        doc_render_phase = PhaseConfig(
            phase_name="DOC_JSON转DOCX",
            task_goal="将最终定稿的 DOC JSON 严格映射为 docx 文件，不允许增补、润色、删改、猜测或臆测。",
            planner_prompt_template=self.prompt_set.doc_render_planner_prompt,
            executor_prompt_template=self.prompt_set.doc_render_executor_prompt,
            prompt_vars={
                "doc_json_path": self.doc_json_path,
            },
            max_step_rounds=self.max_step_rounds,
        )
        all_results.append(self._run_phase(doc_render_phase, self.toolbox_set.doc_render_toolbox))

        print("\n=== 全流程结束 ===")
        print(f"共执行阶段数: {len(all_results)}")
        return all_results


if __name__ == "__main__":
    from Tools import (
        rd_verilog,
        wr_json,
        wr_doc_json,
        doc_json_to_docx,
        wr_doc_feedback_json,
        ToolExecutor,
    )
    from Tools_discription import (
        rd_verilog_description,
        wr_json_description,
        wr_doc_json_description,
        doc_json_to_docx_description,
        wr_doc_feedback_json_description,
    )
    from project_files import mini_test_files
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
        enable_rd_verilog: bool = False,
        enable_wr_json: bool = False,
        enable_wr_doc_json: bool = False,
        enable_wr_doc_feedback_json: bool = False,
        enable_doc_json_to_docx: bool = False,
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

    rate_limiter = LLMRateLimiter(capacity=3, refill_tokens_per_minute=3)

    workflow_agent = IterativeFirmwareDocAgent(
        llm_client=llm_client,
        toolbox_set=toolbox_set,
        project_files=mini_test_files,
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
