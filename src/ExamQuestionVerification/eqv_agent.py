import asyncio
import json
import os
from typing import Literal, Optional
import yaml

from agentscope.agent import ReActAgent
from agentscope.message import Msg, TextBlock
from agentscope.memory import InMemoryMemory, MemoryBase
from agentscope.model import OpenAIChatModel, DashScopeChatModel, ChatModelBase
from agentscope.formatter import DeepSeekChatFormatter, DashScopeChatFormatter, TruncatedFormatterBase
from agentscope.tool import Toolkit, ToolResponse

from prompts import PROMPTS
from schemas import ExamQuestion, VerificationResult

# import agentscope
# agentscope.init(studio_url="http://localhost:3000")


class ExamQuestionVerificationAgent(ReActAgent):
    def __init__(
        self,
        name: str,
        model: ChatModelBase,
        memory: MemoryBase,
        formatter: TruncatedFormatterBase,
        toolkit: Toolkit | None = None,
        sys_prompt: str = PROMPTS["agent_sys_prompt"],
        max_iters: int = 10,
    ) -> None:
        # 先调用父类初始化，避免在调用前设置任何属性
        tools = toolkit or Toolkit()
        super().__init__(
            name=name,
            model=model,
            memory=memory,
            formatter=formatter,
            toolkit=tools,
            sys_prompt=sys_prompt,
            max_iters=max_iters,
        )

        # 初始化考试题目核查器（在父类初始化之后设置属性）
        self.eqv_agent = ReActAgent(
            name="AGENT_EQV",
            sys_prompt=(
                "你是一个专业的考试题目核查器，负责判断考试题目是否合规。"
                "如果题目不合规，请给出修正意见。"
                "请直接输出结果文本或使用工具，不要调用 generate_response 工具时省略参数。"
            ),
            formatter=formatter,
            model=model,
            memory=InMemoryMemory(),
        )
        # 初始化考试题目修正器（在父类初始化之后设置属性）
        self.eqf_agent = ReActAgent(
            name="AGENT_EQF",
            sys_prompt=(
                "你是一个专业的考试题目修正器，负责根据提供的考题和修正意见创建符合要求的新考题。"
                "输出时请直接给出 JSON 格式的考题对象；不要以空参数调用 generate_response。"
            ),
            formatter=formatter,
            model=model,
            memory=InMemoryMemory(),
        )

        # 注册工具到当前 Agent 的 toolkit
        self.toolkit.register_tool_function(self.exam_question_verify_tool)
        self.toolkit.register_tool_function(self.exam_question_fix_tool)

    async def exam_question_verify_tool(
        self,
        question: str,
        answer: str,
        question_type: str,
        knowledge_point: str,
        knowledge_point_description: str,
        extra_requirement: str,
    ) -> ToolResponse:
        """
        核查考试题目是否合规, 若不合规, 给出修正意见(工具函数)

        Args:
            question (str): 考试题目
            answer (str): 考试题目答案
            question_type (str): 考试题目类型
            knowledge_point (str): 考试题目所属的知识点
            knowledge_point_description (str): 考试题目所属的知识点的具体描述
            extra_requirement (str): 考试题目额外要求
        """
        try:
            if question_type in ("single_choice", "单选题"):
                verification_prompt = PROMPTS["single_choice_verification"]
            elif question_type in ("multi_choice", "多选题"):
                verification_prompt = PROMPTS["multi_choice_verification"]
            elif question_type in ("fill_blank", "填空题"):
                verification_prompt = PROMPTS["fill_blank_verification"]
            elif question_type in ("brief_answer", "简答题"):
                verification_prompt = PROMPTS["brief_answer_verification"]
            elif question_type in ("calculation", "计算题"):
                verification_prompt = PROMPTS["calculation_verification"]
            else:
                verification_prompt = PROMPTS["verification_prompt"].format(
                    question_type=question_type,
                )
            verification_prompt = verification_prompt.format(
                question=question,
                answer=answer,
                knowledge_point=knowledge_point,
                knowledge_point_description=knowledge_point_description,
                extra_requirement=extra_requirement,
            )

            res = await self.eqv_agent(Msg("user", role="user", content=verification_prompt), structured_model=VerificationResult)
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"考试题目核查结果:{res.metadata}"
                    ),
                ]
            )
        except Exception as e:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"核查工具调用中断，错误信息：{str(e)}",
                    ),
                ]
            )

    async def exam_question_fix_tool(
        self,
        question: str,
        answer: str,
        question_type: str,
        knowledge_point: str,
        knowledge_point_description: str,
        extra_requirement: str,
        suggestion: str,
    ) -> ToolResponse:
        """
        基于修正意见，修正考题(工具函数)

        Args:
            question (str): 考试题目
            answer (str): 考试题目答案
            question_type (str): 考试题目类型
            knowledge_point (str): 考试题目所属的知识点
            knowledge_point_description (str): 考试题目所属的知识点的具体描述
            extra_requirement (str): 考试题目额外要求
            suggestion (str): 考题修正意见
        """

        try:
            fix_prompt = PROMPTS["fix_prompt"].format(
                question=question,
                answer=answer,
                question_type=question_type,
                knowledge_point=knowledge_point,
                knowledge_point_description=knowledge_point_description,
                extra_requirement=extra_requirement,
                suggestion=suggestion,
            )
            res = await self.eqf_agent(Msg("user", role="user", content=fix_prompt), structured_model=ExamQuestion)
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"修正后的考题:{res.metadata}",
                    ),
                ]
            )
        except Exception as e:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"修正工具调用中断，错误信息：{str(e)}",
                    ),
                ]
            )


async def main():

    conf_path = os.path.join(os.path.dirname(__file__), "conf.yaml")
    with open(conf_path, "r", encoding="utf-8") as f:
        CONF = yaml.safe_load(f)

    LLM_BINDING = CONF.get("LLM_BINDING") or os.getenv("LLM_BINDING") or "deepseek"
    MODEL_NAME = CONF.get("MODEL_NAME") or os.getenv("MODEL_NAME") or "deepseek-chat"
    API_KEY = CONF.get("API_KEY") or os.getenv("API_KEY") or ""
    BASE_URL = CONF.get("BASE_URL") or os.getenv("BASE_URL") or "https://api.deepseek.com"
    if LLM_BINDING == "deepseek":
        model = OpenAIChatModel(
            model_name=MODEL_NAME,
            api_key=API_KEY,
            client_args={"base_url": BASE_URL},
            stream=True,
        )
        formatter = DeepSeekChatFormatter()
    elif LLM_BINDING == "dashscope":
        model = DashScopeChatModel(
            model_name=MODEL_NAME,
            api_key=API_KEY,
            stream=True,
        )
        formatter = DashScopeChatFormatter()
    else:
        raise ValueError(f"不支持的LLM绑定: {LLM_BINDING}")

    agent = ExamQuestionVerificationAgent(
        name="考试题目核查代理",
        model=model,
        formatter=formatter,
        memory=InMemoryMemory()
    )

    exam_question = ExamQuestion(
        question='''
        搜索算法相关\n（1）分别说明 DFS 和 BFS 如何用队列或栈实现，并对比两者遍历同一图时的顺序差异。\n（2）在求解无权图最短路径问题时，为什么 BFS 通常比 DFS 更高效？结合遍历特性解释原因。
        ''',
        answer="（1）DFS 用栈（递归或显式栈），一路深入再回溯；BFS 用队列，一层层扩展；顺序差异：DFS 纵深，BFS 横扩。\n（2）BFS 按层扩展，首次到达目标即最短路径；DFS 可能深入很长非最短路径才回溯，访问节点更多。",
        question_type="简答题",
        knowledge_point="",
        knowledge_point_description="",
        extra_requirement="将简答题修改为填空题",
    )

    query = '''
    核查并修复考试题目:
    考试题目：{question}
    考题答案：{answer}
    考试题目类型：{question_type}
    考试题目所属的知识点：{knowledge_point}
    考试题目所属的知识点的具体描述：{knowledge_point_description}
    考试题目额外要求：{extra_requirement}
    '''.format(**exam_question.model_dump())

    res = await agent(Msg("user", role="user", content=query), structured_model=ExamQuestion)

    print("="*20+f"修正后的考题信息"+"="*20)
    print(res.metadata)
    

if __name__ == "__main__":
    asyncio.run(main())