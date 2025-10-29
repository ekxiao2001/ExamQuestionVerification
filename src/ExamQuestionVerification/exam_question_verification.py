import asyncio
import json
from typing import Literal
import yaml

from agentscope.agent import ReActAgent
from agentscope.message import Msg, TextBlock
from agentscope.memory import InMemoryMemory
from agentscope.model import OpenAIChatModel, DashScopeChatModel, ChatModelBase
from agentscope.formatter import DeepSeekChatFormatter, DashScopeChatFormatter, TruncatedFormatterBase
from agentscope.tool import Toolkit, ToolResponse

from prompts import PROMPTS
from schemas import ExamQuestion, VerificationResult

# import agentscope
# agentscope.init(studio_url="http://localhost:3000")


class ExamQuestionVerification(object):
    '''考试题目检测+修正器'''
    def __init__(self, model: ChatModelBase, formatter: TruncatedFormatterBase):
        """
        初始化考试题目检测+修正器
        Args:
            model (ChatModelBase): 用于考试题目检测+修正的模型
            formatter (TruncatedFormatterBase): 用于考试题目检测+修正的格式化器
        """
        self.model = model
        self.formatter = formatter

    async def main(self, exam_question: ExamQuestion, max_fix_attempts: int = 3) -> ExamQuestion:
        """
        主函数，用于核查和修正考试题目
        Args:
            exam_question (ExamQuestion): 考试题目信息
            max_fix_attempts (int): 最大修正次数. Defaults to 3.
        Returns:
            ExamQuestion: 最终修正后的考试题目
        """
        exam_question_history = [exam_question]
        verification_result_history = []

        for i in range(max_fix_attempts):
            # 核查考题
            print("="*20+f"第{i+1}次核查中"+"="*20)
            verification_result = await self.verify_exam_question(exam_question_history[-1])
            verification_result_history.append(verification_result)

            # 判断是否需要修正考题
            if bool(verification_result.Compliance):
                break
            else:
                print(f"="*20+f"第{i+1}次核查，题目不合规，修正中"+"="*20)
                exam_question = await self.fix_exam_question(exam_question_history[-1], verification_result)
                exam_question_history.append(exam_question)
                print("\n")

        print("="*20+f"最终修正后的考题"+"="*20)
        print(json.dumps(exam_question_history[-1].model_dump(), indent=4, ensure_ascii=False)) # type: ignore

        return exam_question_history[-1]

    async def agent_main(self, exam_question: ExamQuestion, max_fix_attempts: int = 3) -> ExamQuestion:
        """
        主函数，用于核查和修正考试题目(使用ReActAgent)
        Args:
            exam_question (ExamQuestion): 考试题目信息
            max_fix_attempts (int): 最大修正次数. Defaults to 3.
        """
        toolkit = Toolkit()
        toolkit.register_tool_function(self.verify_exam_question_tool)
        toolkit.register_tool_function(self.fix_exam_question_tool)
        json_schemas = toolkit.get_json_schemas()
        print(json_schemas)

        main_agent = ReActAgent(
            name="MAIN_AGENT_exam_question_verification",
            sys_prompt=f'''你是一个专业的考试题目核查+修正器，你负责：
            1. 判断考试题目是否合规。如果题目不合规，则给出修正意见。
            2. 如果题目不合规，则根据修正意见修正考题。最多修正{max_fix_attempts}次；如果题目合规，则直接输出考题信息。
            ''',
            formatter=self.formatter,
            model=self.model,
            memory=InMemoryMemory(),
            toolkit=toolkit,
        )
        query = '''
        考试题目：{question}
        考试题目类型：{question_type}
        考试题目所属的知识点：{knowledge_point}
        考试题目所属的知识点的具体描述：{knowledge_point_description}
        考试题目额外要求：{extra_requirement}
        '''
        res = await main_agent(Msg("user", role="user", content=query.format(**exam_question.model_dump())), structured_model=ExamQuestion)

        print("="*20+f"修正后的考题"+"="*20)
        print(res.metadata)

        return ExamQuestion(**res.metadata) # type: ignore

    async def verify_exam_question(self, exam_question: ExamQuestion) -> VerificationResult:
        """
        核查考试题目是否合规, 若不合规, 给出修正意见

        Args:
            exam_question (ExamQuestion): 考试题目信息
        Returns:
            VerificationResult: 考试题目核查结果
        """

        agent = ReActAgent(
            name="AGENT_exam_question_verification",
            sys_prompt="你是一个专业的考试题目核查器，负责判断考试题目是否合规。如果题目不合规，请给出修正意见。",
            formatter=self.formatter,
            model=self.model,
            memory=InMemoryMemory(),
        )

        if exam_question.question_type in ("single_choice", "单选题"):
            verification_prompt = PROMPTS["single_choice_verification"]
        elif exam_question.question_type in ("multi_choice", "多选题"):
            verification_prompt = PROMPTS["multi_choice_verification"]
        elif exam_question.question_type in ("fill_blank", "填空题"):
            verification_prompt = PROMPTS["fill_blank_verification"]
        elif exam_question.question_type in ("brief_answer", "简答题"):
            verification_prompt = PROMPTS["brief_answer_verification"]
        elif exam_question.question_type in ("calculation", "计算题"):
            verification_prompt = PROMPTS["calculation_verification"]
        else:
            verification_prompt = PROMPTS["verification_prompt"].format(
                question_type=exam_question.question_type,
            )
        verification_prompt = verification_prompt.format(
            question=exam_question.question,
            answer=exam_question.answer,
            knowledge_point=exam_question.knowledge_point,
            knowledge_point_description=exam_question.knowledge_point_description,
            extra_requirement=exam_question.extra_requirement,
        )
    
        res = await agent(Msg("user", role="user", content=verification_prompt), structured_model=VerificationResult)
        # print(res)
        return VerificationResult(**res.metadata) # type: ignore

    async def verify_exam_question_tool(self, exam_question: ExamQuestion) -> ToolResponse:
        """
        核查考试题目是否合规, 若不合规, 给出修正意见(工具函数)

        Args:
            exam_question (ExamQuestion): 考试题目信息

        Returns:
            VerificationResult: 考试题目核查结果
        """
        # 确保exam_question是ExamQuestion对象而不是字典
        if isinstance(exam_question, dict):
            # 如果是字典，转换为ExamQuestion对象
            exam_question = ExamQuestion(**exam_question)

        agent = ReActAgent(
            name="AGENT_exam_question_verification",
            sys_prompt="你是一个专业的考试题目核查器，负责判断考试题目是否合规。如果题目不合规，请给出修正意见。",
            formatter=self.formatter,
            model=self.model,
            memory=InMemoryMemory(),
        )

        if exam_question.question_type in ("single_choice", "单选题"):
            verification_prompt = PROMPTS["single_choice_verification"]
        elif exam_question.question_type in ("multi_choice", "多选题"):
            verification_prompt = PROMPTS["multi_choice_verification"]
        elif exam_question.question_type in ("fill_blank", "填空题"):
            verification_prompt = PROMPTS["fill_blank_verification"]
        elif exam_question.question_type in ("calculation", "计算题"):
            verification_prompt = PROMPTS["calculation_verification"]
        else:
            verification_prompt = PROMPTS["verification_prompt"].format(
                question_type=exam_question.question_type,
            )
        verification_prompt = verification_prompt.format(
            question=exam_question.question,
            answer=exam_question.answer,
            knowledge_point=exam_question.knowledge_point,
            knowledge_point_description=exam_question.knowledge_point_description,
            extra_requirement=exam_question.extra_requirement,
        )

        res = await agent(Msg("user", role="user", content=verification_prompt), structured_model=VerificationResult)
        # print(res.metadata)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f'''
                    考试题目及大纲:{json.dumps(exam_question.model_dump(), ensure_ascii=False)}
                    考试题目核查结果:{json.dumps(res.metadata, ensure_ascii=False)}
                    '''
                ),
            ]
        )

    async def fix_exam_question(self, exam_question: ExamQuestion, verification_result: VerificationResult) -> ExamQuestion:
        """
        基于核查结果修正考题
        Args:
            exam_question (ExamQuestion): 考试题目信息
            verification_result (VerificationResult): 考试题目核查结果

        Returns:
            ExamQuestion: 修正后的考试题目信息
        """
        if bool(verification_result.Compliance):
            return exam_question
        else:
            agent = ReActAgent(
                name="AGENT_exam_question_fix",
                sys_prompt="你是一个专业的考试题目修正器，负责根据提供的考题和修正意见创建符合要求的新考题。",
                formatter=self.formatter,
                model=self.model,
                memory=InMemoryMemory(),
            )
            fix_prompt = PROMPTS["fix_prompt"].format(
                question=exam_question.question,
                answer=exam_question.answer,
                question_type=exam_question.question_type,
                knowledge_point=exam_question.knowledge_point,
                knowledge_point_description=exam_question.knowledge_point_description,
                extra_requirement=exam_question.extra_requirement,
                suggestion=verification_result.suggestion,
            )
            res = await agent(Msg("user", role="user", content=fix_prompt), structured_model=ExamQuestion)
            # print(res.metadata)
            return ExamQuestion(**res.metadata) # type: ignore

    async def fix_exam_question_tool(self, exam_question: ExamQuestion, verification_result: VerificationResult) -> ToolResponse:
        """
        基于核查结果修正考题(工具函数)
        Args:
            exam_question (ExamQuestion): 考试题目信息
            verification_result (VerificationResult): 考试题目核查结果

        Returns:
            ExamQuestion: 修正后的考试题目信息
        """

        # 确保exam_question是ExamQuestion对象而不是字典
        if isinstance(exam_question, dict):
            # 如果是字典，转换为ExamQuestion对象
            exam_question = ExamQuestion(**exam_question)
        # 确保verification_result是VerificationResult对象而不是字典
        if isinstance(verification_result, dict):
            # 如果是字典，转换为VerificationResult对象
            verification_result = VerificationResult(**verification_result)

        if bool(verification_result.Compliance):
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=json.dumps(exam_question.model_dump(), ensure_ascii=False),
                    )
                ]
            )
        else:
            agent = ReActAgent(
                name="AGENT_exam_question_fix",
                sys_prompt="你是一个专业的考试题目修正器，负责根据提供的考题和修正意见创建符合要求的新考题。",
                formatter=self.formatter,
                model=self.model,
                memory=InMemoryMemory(),
            )
            fix_prompt = PROMPTS["fix_prompt"].format(
                question=exam_question.question,
                answer=exam_question.answer,
                question_type=exam_question.question_type,
                knowledge_point=exam_question.knowledge_point,
                knowledge_point_description=exam_question.knowledge_point_description,
                extra_requirement=exam_question.extra_requirement,
                suggestion=verification_result.suggestion,
            )
            res = await agent(Msg("user", role="user", content=fix_prompt), structured_model=ExamQuestion)
            # print(res.metadata)
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=json.dumps(res.metadata, ensure_ascii=False),
                    )
                ]
            )


def build_exam_verifier(
    llm_binding: Literal["deepseek", "dashscope"],
    model_name: str,
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    stream: bool = True,
) -> ExamQuestionVerification:
    try:
        if llm_binding == "deepseek":
            formatter = DeepSeekChatFormatter()
            model = OpenAIChatModel(
                model_name=model_name,
                api_key=api_key,
                stream=stream,
                client_args={"base_url": base_url},
            )
        elif llm_binding == "dashscope":
            formatter = DashScopeChatFormatter()
            model = DashScopeChatModel(
                model_name=model_name,
                api_key=api_key,
                stream=stream,
            )

        return ExamQuestionVerification(
            formatter=formatter,
            model=model
        )
    except Exception as e:
        raise RuntimeError(f"加载模型失败: {e}")


if __name__ == "__main__":
    # 加载配置文件
    with open('conf.yaml', 'r', encoding='utf-8') as f:
        conf = yaml.safe_load(f)
        model_name = conf.get('MODEL_NAME', 'qwen-plus')
        api_key = conf.get('API_KEY', None)
        base_url = conf.get('BASE_URL', None)

    # 创建ExamQuestionVerification实例
    exam_question_verification = ExamQuestionVerification(
        formatter=DeepSeekChatFormatter(),
        model=OpenAIChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=False,
            client_args={"base_url": base_url},
        ),
    )

    # 模拟考试题目
    exam_question = ExamQuestion(
        question='''
        搜索算法相关\n（1）分别说明 DFS 和 BFS 如何用队列或栈实现，并对比两者遍历同一图时的顺序差异。\n（2）在求解无权图最短路径问题时，为什么 BFS 通常比 DFS 更高效？结合遍历特性解释原因。
        ''',
        answer="（1）DFS 用栈（递归或显式栈），一路深入再回溯；BFS 用队列，一层层扩展；顺序差异：DFS 纵深，BFS 横扩。\n（2）BFS 按层扩展，首次到达目标即最短路径；DFS 可能深入很长非最短路径才回溯，访问节点更多。",
        question_type="简答题",
        knowledge_point="",
        knowledge_point_description="",
        extra_requirement="",
    )

    # 运行考试题目核查
    new_exam_question = asyncio.run(exam_question_verification.main(exam_question, max_fix_attempts=3))