import ast
import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional
from threading import Lock

from LLM_class import HelloAgentsLLM


@dataclass
class PhaseConfig:
    """
    描述一次 Plan-and-Solve 阶段所需的全部配置。
    """
    phase_name: str
    task_goal: str
    planner_prompt_template: str
    executor_prompt_template: str
    prompt_vars: Dict[str, Any] = field(default_factory=dict)
    max_step_rounds: int = 8


class LLMRateLimiter:
    """
    令牌桶限流器：
    - 桶容量 capacity
    - 每分钟补充 refill_tokens_per_minute 个令牌
    - 每次 acquire() 消耗 1 个令牌
    """

    def __init__(self, capacity: int = 3, refill_tokens_per_minute: float = 3.0):
        if capacity <= 0:
            raise ValueError("capacity 必须大于 0")
        if refill_tokens_per_minute <= 0:
            raise ValueError("refill_tokens_per_minute 必须大于 0")

        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_tokens_per_minute = float(refill_tokens_per_minute)
        self.refill_rate_per_second = self.refill_tokens_per_minute / 60.0
        self.last_refill_time = time.time()
        self._lock = Lock()

    def _refill(self):
        """
        按距离上次补充的时间，自动补充令牌。
        """
        now = time.time()
        elapsed = now - self.last_refill_time
        if elapsed <= 0:
            return

        added_tokens = elapsed * self.refill_rate_per_second
        if added_tokens > 0:
            self.tokens = min(self.capacity, self.tokens + added_tokens)
            self.last_refill_time = now

    def acquire(self):
        """
        获取 1 个令牌。
        若当前没有足够令牌，则等待到补足 1 个令牌再继续。
        """
        while True:
            with self._lock:
                self._refill()

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    print(f"🎫 获取 1 个令牌，剩余令牌: {self.tokens:.2f}/{self.capacity:.0f}")
                    return

                # 还差多少令牌才能到 1
                needed_tokens = 1.0 - self.tokens
                wait_seconds = needed_tokens / self.refill_rate_per_second

                print(
                    f"⏳ 当前令牌不足，剩余 {self.tokens:.2f}/{self.capacity:.0f}，"
                    f"预计等待 {wait_seconds:.1f} 秒后继续..."
                )

            time.sleep(wait_seconds)


class Planner:
    def __init__(
        self,
        llm_client,
        toolbox,
        planner_prompt_template: str,
        context_provider,
        rate_limiter: Optional[LLMRateLimiter] = None,
    ):
        self.llm_client = llm_client
        self.toolbox = toolbox
        self.planner_prompt_template = planner_prompt_template
        self.context_provider = context_provider
        self.rate_limiter = rate_limiter

    def _think(self, messages: List[Dict[str, str]]) -> str:
        if self.rate_limiter is not None:
            self.rate_limiter.acquire()
        return self.llm_client.think(messages=messages) or ""

    def _parse_plan(self, response_text: str) -> List[str]:
        """
        尝试从 LLM 输出中解析计划列表。
        优先解析 ```python ``` 代码块中的列表；
        若失败，再尝试直接整体解析；
        再失败则按行解析。
        """
        text = response_text.strip()

        match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
        if match:
            plan_str = match.group(1).strip()
            try:
                plan = ast.literal_eval(plan_str)
                if isinstance(plan, list):
                    return [str(x) for x in plan]
            except Exception:
                pass

        try:
            plan = ast.literal_eval(text)
            if isinstance(plan, list):
                return [str(x) for x in plan]
        except Exception:
            pass

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        numbered_items = []
        for line in lines:
            line = re.sub(r"^\d+[\.\)]\s*", "", line)
            if line:
                numbered_items.append(line)

        return numbered_items

    def build_prompt(self) -> str:
        context = self.context_provider()
        return self.planner_prompt_template.format(**context)

    def plan(self) -> List[str]:
        prompt = self.build_prompt()
        messages = [{"role": "user", "content": prompt}]

        print("--- 正在生成计划 ---")
        response_text = self._think(messages)
        print(f"✅ 计划已生成:\n{response_text}")

        plan = self._parse_plan(response_text)
        if not plan:
            print("❌ 未能解析出有效计划。")
        return plan


class Executor:
    def __init__(
        self,
        llm_client,
        toolbox,
        executor_prompt_template: str,
        context_provider,
        max_step_rounds: int = 8,
        rate_limiter: Optional[LLMRateLimiter] = None,
    ):
        self.llm_client = llm_client
        self.toolbox = toolbox
        self.executor_prompt_template = executor_prompt_template
        self.context_provider = context_provider
        self.max_step_rounds = max_step_rounds
        self.rate_limiter = rate_limiter

    def _think(self, messages: List[Dict[str, str]]) -> str:
        if self.rate_limiter is not None:
            self.rate_limiter.acquire()
        return self.llm_client.think(messages=messages) or ""

    def _extract_action(self, text: str) -> Optional[Dict[str, Any]]:
        """
        解析格式：
        Action: rd_verilog
        Action Input: {"file_path": "...", "start": null, "end": null}
        """
        action_match = re.search(r"Action:\s*([a-zA-Z_][a-zA-Z0-9_]*)", text)
        input_match = re.search(r"Action Input:\s*(\{.*\})", text, re.DOTALL)

        if not action_match or not input_match:
            return None

        tool_name = action_match.group(1).strip()
        raw_input = input_match.group(1).strip()

        try:
            tool_input = json.loads(raw_input)
        except json.JSONDecodeError:
            try:
                tool_input = ast.literal_eval(raw_input)
            except Exception:
                return {
                    "tool_name": tool_name,
                    "tool_input": None,
                    "parse_error": f"无法解析 Action Input: {raw_input}",
                }

        if not isinstance(tool_input, dict):
            return {
                "tool_name": tool_name,
                "tool_input": None,
                "parse_error": "Action Input 解析结果不是 dict。",
            }

        return {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "parse_error": None,
        }

    def _extract_final_answer(self, text: str) -> Optional[str]:
        match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _extract_step_answer(self, text: str) -> Optional[str]:
        match = re.search(r"Step Answer:\s*(.*)", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _build_messages(
        self,
        plan: List[str],
        history: str,
        current_step: str,
        scratchpad: str
    ) -> List[Dict[str, str]]:
        context = self.context_provider()
        context.update({
            "plan": json.dumps(plan, ensure_ascii=False, indent=2),
            "history": history if history else "无",
            "current_step": current_step,
            "scratchpad": scratchpad if scratchpad else "无",
        })

        prompt = self.executor_prompt_template.format(**context)
        return [{"role": "user", "content": prompt}]

    def _call_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        tool_func = self.toolbox.getTool(tool_name)
        if tool_func is None:
            return {
                "success": False,
                "message": f"未知工具: {tool_name}",
                "data": None,
                "tool_help": self.toolbox.getAvailableTools(),
            }

        try:
            raw_result = tool_func(**tool_input)
            # 统一包装不同工具的返回格式
            success = True
            message = f"工具 {tool_name} 调用成功。"

            if isinstance(raw_result, dict):
                if "success" in raw_result:
                    success = bool(raw_result["success"])
                    message = raw_result.get("message", message)
                elif "read_ok" in raw_result:
                    success = bool(raw_result["read_ok"])
                    message = raw_result.get("error", "") if not success else message
                elif "write_ok" in raw_result:
                    success = bool(raw_result["write_ok"])
                    message = raw_result.get("error", "") if not success else message

            return {
                "success": success,
                "message": message,
                "data": raw_result,
                "tool_help": None if success else self.toolbox.getAvailableTools(),
            }

        except TypeError as e:
            return {
                "success": False,
                "message": f"工具 {tool_name} 参数错误: {e}",
                "data": None,
                "tool_help": self.toolbox.getAvailableTools(),
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"工具 {tool_name} 调用失败: {type(e).__name__}: {e}",
                "data": None,
                "tool_help": self.toolbox.getAvailableTools(),
            }

    def _is_tool_success(self, tool_result: Dict[str, Any]) -> bool:
        return bool(tool_result.get("success", False))

    def _compact_tool_result(self, tool_result: Dict[str, Any], max_source_chars: int = 4000) -> Dict[str, Any]:
        """
        压缩工具返回结果，避免 history 过长。
        对 rd_verilog 的 source_code 做截断保留。
        """
        if not isinstance(tool_result, dict):
            return {"raw_result": str(tool_result)}

        compact = dict(tool_result)

        if "source_code" in compact and isinstance(compact["source_code"], str):
            source = compact["source_code"]
            if len(source) > max_source_chars:
                compact["source_code"] = source[:max_source_chars] + "\\n...<源码过长，已截断>..."

        return compact

    def _execute_one_step(self, plan: List[str], history: str, current_step: str) -> str:
        scratchpad = ""

        for round_idx in range(1, self.max_step_rounds + 1):
            print(f"   [步骤内推理轮次 {round_idx}/{self.max_step_rounds}]")

            messages = self._build_messages(
                plan=plan,
                history=history,
                current_step=current_step,
                scratchpad=scratchpad,
            )

            response_text = self._think(messages)
            print(f"   LLM输出:\n{response_text}")

            final_answer = self._extract_final_answer(response_text)
            if final_answer is not None:
                return f"Final Answer: {final_answer}"

            step_answer = self._extract_step_answer(response_text)
            if step_answer is not None:
                return step_answer

            action_info = self._extract_action(response_text)
            if action_info is None:
                scratchpad += (
                    "\n[系统反馈]\n"
                    "未检测到合法的 Action / Action Input，也未检测到 Step Answer / Final Answer。\n"
                    "请严格按指定格式输出。\n"
                )
                continue

            if action_info.get("parse_error"):
                scratchpad += (
                    "\n[系统反馈]\n"
                    f"工具参数解析失败: {action_info['parse_error']}\n"
                    "请重新输出合法 JSON 格式的 Action Input。\n"
                )
                continue

            tool_name = action_info["tool_name"]
            tool_input = action_info["tool_input"]

            print(f"   -> 调用工具: {tool_name}")
            print(f"   -> 工具输入: {tool_input}")

            tool_result = self._call_tool(tool_name, tool_input)

            # 1. 工具调用成功：当前步骤立刻结束，跳转到下一步
            if self._is_tool_success(tool_result):
                compact_result = self._compact_tool_result(tool_result)
                return (
                    f"工具调用成功: {tool_name}\\n"
                    f"Observation: {json.dumps(compact_result, ensure_ascii=False)}"
                )

            # 2. 工具调用失败：保留到 scratchpad，让模型在本步骤内重试
            scratchpad += (
                f"\\n[工具调用记录]\\n"
                f"Action: {tool_name}\\n"
                f"Action Input: {json.dumps(tool_input, ensure_ascii=False)}\\n"
                f"Observation: {json.dumps(tool_result, ensure_ascii=False)}\\n"
                f"[系统反馈]\\n"
                f"工具调用失败，请根据失败信息修正参数或调整方案。\\n"
                f"该工具的正确用法如下：\\n{tool_result.get('tool_help', '无可用说明')}\\n"
            )

        return f"步骤执行失败：超过最大推理轮次 {self.max_step_rounds}，仍未完成。"

    def execute(self, plan: List[str]) -> str:
        # 只保留最近 10 步的历史，避免 history 持续膨胀
        history_buffer: Deque[str] = deque(maxlen=50)
        final_answer = ""

        print("\n--- 正在执行计划 ---")

        for i, step in enumerate(plan):
            print(f"\n-> 正在执行步骤 {i + 1}/{len(plan)}: {step}")

            current_history = "\n".join(history_buffer) if history_buffer else ""

            step_result = self._execute_one_step(
                plan=plan,
                history=current_history,
                current_step=step,
            )

            if step_result.startswith("Final Answer:"):
                final_answer = step_result.replace("Final Answer:", "", 1).strip()
                print(f"✅ 提前得到最终答案: {final_answer}")
                return final_answer

            history_buffer.append(f"步骤 {i + 1}: {step}\n结果: {step_result}\n")
            print(f"✅ 步骤 {i + 1} 已完成，结果: {step_result}")

            final_answer = step_result

        return final_answer


class PlanAndSolveAgent:
    """
    通用的、提示词可插拔的 Plan-and-Solve 模块。
    任何阶段只要传入不同的 PhaseConfig，就可以复用这一套逻辑。
    """
    def __init__(
        self,
        llm_client,
        toolbox,
        project_files: str,
        json_db_path: str,
        output_doc_path: str,
        phase_config: PhaseConfig,
        rate_limiter: Optional[LLMRateLimiter] = None,
    ):
        self.llm_client = llm_client
        self.toolbox = toolbox
        self.project_files = project_files
        self.json_db_path = json_db_path
        self.output_doc_path = output_doc_path
        self.phase_config = phase_config
        self.rate_limiter = rate_limiter

        self.planner = Planner(
            llm_client=self.llm_client,
            toolbox=self.toolbox,
            planner_prompt_template=self.phase_config.planner_prompt_template,
            context_provider=self._build_base_context,
            rate_limiter=self.rate_limiter,
        )

        self.executor = Executor(
            llm_client=self.llm_client,
            toolbox=self.toolbox,
            executor_prompt_template=self.phase_config.executor_prompt_template,
            context_provider=self._build_base_context,
            max_step_rounds=self.phase_config.max_step_rounds,
            rate_limiter=self.rate_limiter,
        )

    def _build_base_context(self) -> Dict[str, Any]:
        context = {
            "task_goal": self.phase_config.task_goal,
            "project_files": self.project_files,
            "json_db_path": self.json_db_path,
            "output_doc_path": self.output_doc_path if self.output_doc_path else "未设置",
            "tools": self.toolbox.getAvailableTools(),
        }
        context.update(self.phase_config.prompt_vars or {})
        return context

    def run(self) -> Dict[str, Any]:
        print(f"\n--- 开始处理阶段 ---\n阶段: {self.phase_config.phase_name}")
        print(f"任务目标: {self.phase_config.task_goal}")

        plan = self.planner.plan()
        if not plan:
            print("\n--- 阶段终止 ---\n无法生成有效的行动计划。")
            return {
                "phase_name": self.phase_config.phase_name,
                "task_goal": self.phase_config.task_goal,
                "plan": [],
                "final_answer": None,
                "success": False,
            }

        print("\n--- 最终计划 ---")
        for idx, p in enumerate(plan, 1):
            print(f"{idx}. {p}")

        final_answer = self.executor.execute(plan)

        print(f"\n--- 阶段完成 ---\n最终答案: {final_answer}")
        return {
            "phase_name": self.phase_config.phase_name,
            "task_goal": self.phase_config.task_goal,
            "plan": plan,
            "final_answer": final_answer,
            "success": True,
        }


if __name__ == "__main__":
    from Tools import rd_verilog, wr_json, wr_doc, ToolExecutor
    from Tools_discription import (
        rd_verilog_description,
        wr_json_description,
        wr_doc_description,
    )
    from project_files import project_files_text
    from prompt_workflow_old import (
        INIT_PLANNER_PROMPT_TEMPLATE,
        INIT_EXECUTOR_PROMPT_TEMPLATE,
    )

    llm_client = HelloAgentsLLM()

    toolbox = ToolExecutor()
    toolbox.registerTool("rd_verilog", rd_verilog_description, rd_verilog)
    toolbox.registerTool("wr_json", wr_json_description, wr_json)

    rate_limiter = LLMRateLimiter(capacity=3, refill_tokens_per_minute=3)

    phase_config = PhaseConfig(
        phase_name="初始化写JSON",
        task_goal="生成每个 Verilog 文件的摘要 JSON，供后续分析。",
        planner_prompt_template=INIT_PLANNER_PROMPT_TEMPLATE,
        executor_prompt_template=INIT_EXECUTOR_PROMPT_TEMPLATE,
        prompt_vars={
            "modify_round": 1,
            "feedback_round": 0,
            "max_feedback_rounds": 3,
        },
        max_step_rounds=8,
    )

    agent = PlanAndSolveAgent(
        llm_client=llm_client,
        toolbox=toolbox,
        project_files=project_files_text,
        json_db_path=".statement.json",
        output_doc_path=".statement.docx",
        phase_config=phase_config,
        rate_limiter=rate_limiter,
    )

    result = agent.run()
    print(result)
