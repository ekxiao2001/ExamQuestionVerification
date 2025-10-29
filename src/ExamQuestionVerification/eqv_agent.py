import os
import asyncio
import socket
from typing import List, Dict, AsyncGenerator, Optional
import concurrent.futures

from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.sandbox.tools.function_tool import function_tool
from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.sandbox_service import SandboxService
from agentscope_runtime.engine.services.environment_manager import EnvironmentManager
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    RunStatus,
    AgentRequest,
)

from agentscope.model import OpenAIChatModel, DashScopeChatModel
from agentscope.agent import ReActAgent
from agentscope.formatter import DeepSeekChatFormatter, DashScopeChatFormatter

from exam_question_verification import build_exam_verifier
from schemas import ExamQuestion, VerificationResult
from prompts import PROMPTS

# ---------------------------
# 加载配置文件
# ---------------------------
import yaml
conf_path = os.path.join(os.path.dirname(__file__), "conf.yaml")
with open(conf_path, "r", encoding="utf-8") as f:
    CONF = yaml.safe_load(f)

# ---------------------------
# 考试题目核查+修正工具实例构建
# ---------------------------
LLM_BINDING = CONF.get("LLM_BINDING") or os.getenv("LLM_BINDING") or "deepseek"
MODEL_NAME = CONF.get("MODEL_NAME") or os.getenv("MODEL_NAME") or "deepseek-chat"
API_KEY = CONF.get("API_KEY") or os.getenv("API_KEY") or ""
BASE_URL = CONF.get("BASE_URL") or os.getenv("BASE_URL") or "https://api.deepseek.com"

verifier = build_exam_verifier(
    llm_binding=LLM_BINDING if LLM_BINDING in ("deepseek", "dashscope") else "deepseek",
    model_name=MODEL_NAME,
    api_key=API_KEY,
    base_url=BASE_URL,
    stream=False
)

@function_tool(name="verify_exam_question_tool")
def verify_exam_question_tool(
    question: str,
    answer: str,
    question_type: str,
    knowledge_point: str = "",
    knowledge_point_description: str = "",
    extra_requirement: Optional[str] = None,
) -> dict:
    """
    核查考题是否合规，返回核查结果和建议。
    
    Args:
        question: 考试题目
        answer: 考试题目答案
        question_type: 考试题目类型
        knowledge_point: 考试题目所属的知识点
        knowledge_point_description: 考试题目所属的知识点的具体描述
        extra_requirement: 考试题目额外要求
    
    Returns:
        dict: 包含核查结果和建议的字典。
    """
    eq = ExamQuestion(
        question=question,
        answer=answer,
        question_type=question_type,
        knowledge_point=knowledge_point,
        knowledge_point_description=knowledge_point_description,
        extra_requirement=extra_requirement,
    )

    def _run_verify():
        return asyncio.run(verifier.verify_exam_question(eq))

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future = executor.submit(_run_verify)
        res = future.result()

    return res.model_dump()

@function_tool(name="fix_exam_question_tool")
def fix_exam_question_tool(
    Compliance: bool,
    suggestion: str,
    question: str,
    answer: str,
    question_type: str,
    knowledge_point: str = "",
    knowledge_point_description: str = "",
    extra_requirement: Optional[str] = None,
) -> dict:
    """
    基于核查结果修正考题，返回修正后的考题。
    
    Args:
        Compliance: 考试题目是否合规
        suggestion: 考试题目修正建议
        question: 考试题目
        answer: 考试题目答案
        question_type: 考试题目类型
        knowledge_point: 考试题目所属的知识点
        knowledge_point_description: 考试题目所属的知识点的具体描述
        extra_requirement: 考试题目额外要求
    
    Returns:
        dict: 修正后的考题对象的字典。
    """
    eq = ExamQuestion(
        question=question,
        answer=answer,
        question_type=question_type,
        knowledge_point=knowledge_point,
        knowledge_point_description=knowledge_point_description,
        extra_requirement=extra_requirement,
    )   
    vr = VerificationResult(
        Compliance=Compliance,
        suggestion=suggestion,
    )

    def _run_fix():
        return asyncio.run(verifier.fix_exam_question(eq, vr))

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future = executor.submit(_run_fix)
        new_eq = future.result()

    return new_eq.model_dump()

@function_tool(name="verify_and_fix_exam_question_tool")
def verify_and_fix_exam_question_tool(
    question: str,
    answer: str,
    question_type: str,
    knowledge_point: str = "",
    knowledge_point_description: str = "",
    extra_requirement: Optional[str] = None,
) -> dict:
    """
    一键核查和修正考题。
    
    Args:
        question: 考试题目
        answer: 考试题目答案
        question_type: 考试题目类型
        knowledge_point: 考试题目所属的知识点
        knowledge_point_description: 考试题目所属的知识点的具体描述
        extra_requirement: 考试题目额外要求
    
    Returns:
        dict: 核查并修复后的考题。
    """
    eq = ExamQuestion(
        question=question,
        answer=answer,
        question_type=question_type,
        knowledge_point=knowledge_point,
        knowledge_point_description=knowledge_point_description,
        extra_requirement=extra_requirement,
    )

    max_fix_attempts = int(CONF.get("MAX_FIX_ATTEMPTS", "3") or "3")
    def _run_verify_and_fix():
        return asyncio.run(verifier.main(eq, max_fix_attempts))

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future = executor.submit(_run_verify_and_fix)
        res = future.result()

    return res.model_dump()


class ExamQuestionVerificationAgent:
    def __init__(self) -> None:
        self.llm_binding = LLM_BINDING
        self.model_name = MODEL_NAME
        self.api_key = API_KEY
        self.base_url = BASE_URL

        self.tools = [
            verify_exam_question_tool,
            fix_exam_question_tool,
            verify_and_fix_exam_question_tool
        ]

        self.agent = self.create_exam_question_verification_agent()

        self.connected = False

    async def connect(self, session_id: str, user_id: str) -> None:
        """
        连接到沙箱环境，初始化会话历史、内存服务、沙箱服务和上下文管理器。
        Args:
            session_id: 会话历史服务和沙箱服务的会话ID
            user_id: 会话历史服务和沙箱服务的用户ID
        """
        # 初始化会话历史服务
        session_history_service = InMemorySessionHistoryService()
        await session_history_service.create_session(session_id, user_id)

        # 初始化内存服务
        self.memory_service = InMemoryMemoryService()
        await self.memory_service.start()

        # 初始化沙箱
        # TODO: 连接远程沙箱应该连接到什么类型的沙箱，base、browser or filesystem？
        # sandbox_type = os.getenv("AGENT_RUNTIME_SANDBOX_TYPE") or "local"
        # if sandbox_type == "local":
        #     self.sandbox_service = SandboxService()
        # elif sandbox_type == "remote":
        #     sandbox_host = CONF.get("AGENT_RUNTIME_SANDBOX_HOST") or os.getenv("AGENT_RUNTIME_SANDBOX_HOST", "localhost")
        #     sandbox_port = CONF.get("AGENT_RUNTIME_SANDBOX_PORT") or os.getenv("AGENT_RUNTIME_SANDBOX_PORT", "8002")
        #     sandbox_url = f"http://{sandbox_host}:{sandbox_port}"
        #     self.sandbox_service = SandboxService(
        #         base_url=sandbox_url,
        #     )
        # else:
        #     raise ValueError(f"不支持的沙箱类型: {sandbox_type}, 请选择 'local' 或 'remote'")
        # await self.sandbox_service.start()
    
        # 创建上下文管理器
        self.context_manager = ContextManager(
            memory_service=self.memory_service,
            session_history_service=session_history_service
        )
        # 创建环境管理器
        # self.environment_manager = EnvironmentManager(
        #     sandbox_service=self.sandbox_service,
        # )

        # 若需要使用沙箱工具
        # from agentscope_runtime.sandbox.tools.filesystem import read_file
        # sandboxes = self.sandbox_service.connect(
        #     session_id=session_id,
        #     user_id=user_id,
        #     tools=[],
        # )
        # print(f"配置了{len(sandboxes)}个沙箱")

        runer = Runner(
            agent=self.agent,
            context_manager=self.context_manager,
            # environment_manager=self.environment_manager,
        )
        self.runner = runer
        self.connected = True

    async def chat(
        self,
        session_id: str,
        user_id: str,
        chat_messages: List[Message],
    ) -> AsyncGenerator[Dict, None]:
        if not self.connected:
            await self.connect(session_id, user_id)

        convert_messages = []
        for chat_message in chat_messages:
            convert_messages.append(
                Message(
                    role=chat_message.role,
                    content=chat_message.content,
                )
            )
        request = AgentRequest(input=convert_messages, session_id=session_id)
        request.tools = []
        async for message in self.runner.stream_query(
            user_id=user_id,
            request=request,
        ):
            if (
                message.object == "message"
                and RunStatus.Completed == message.status
            ):
                yield message.content
    
    async def deploy(self) -> None:
        """部署agent"""
        if not self.connected:
            raise ValueError("代理未包装为Runner环境, 请先调用 connect 方法。")
        
        host = CONF.get("AGENT_RUNTIME_HOST") or os.getenv("AGENT_RUNTIME_HOST", "0.0.0.0")
        port = int(CONF.get("AGENT_RUNTIME_PORT") or os.getenv("AGENT_RUNTIME_PORT", "8001"))
        endpoint_path = CONF.get("AGENT_RUNTIME_ENDPOINT_PATH") or os.getenv("AGENT_RUNTIME_ENDPOINT_PATH", "")

        def _get_accessible_host(host: str) -> str:
            """获取可访问的主机IP地址。"""
            try:
                if host in ("0.0.0.0", "", None):
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        s.connect(("8.8.8.8", 80))
                        ip = s.getsockname()[0]
                    except Exception:
                        ip = socket.gethostbyname(socket.gethostname())
                        if ip.startswith("127."):
                            ip = "127.0.0.1"
                    finally:
                        s.close()
                    return ip
                return host
            except Exception:
                return "127.0.0.1"

        deploy_manager = LocalDeployManager(
            host=_get_accessible_host(host),
            port=port,
        )
        deploy_result = await self.runner.deploy(
            deploy_manager=deploy_manager,
            endpoint_path=endpoint_path,
            stream=True,
        )

        # print(f"🚀智能体部署在: {deploy_result}")
        # print(f"🌐服务URL: http://{host}:{port}")
        # print(f"💚 健康检查: http://{host}:{port}/health")

        await asyncio.Event().wait()

    async def close(self) -> None:
        """关闭所有服务与沙箱连接。"""
        await self.memory_service.stop()
        # await self.sandbox_service.stop()

    def create_exam_question_verification_agent(self) -> AgentScopeAgent:
        """创建考试问题核查智能体。"""

        # 主代理用流式模型，支持异步迭代输出
        if self.llm_binding == "deepseek":
            model = OpenAIChatModel(
                model_name=self.model_name,
                api_key=self.api_key,
                client_args={"base_url": self.base_url},
                stream=True,
            )
            formatter = DeepSeekChatFormatter()
        elif self.llm_binding == "dashscope":
            model = DashScopeChatModel(
                model_name=self.model_name,
                api_key=self.api_key,
                stream=True,
            )
            formatter = DashScopeChatFormatter()
        else:
            raise ValueError(f"不支持的LLM绑定: {self.llm_binding}")

        return AgentScopeAgent(
            name="eqv_plan_agent",
            model=model,
            tools=self.tools,
            agent_config={
                "sys_prompt": PROMPTS["agent_sys_prompt"],
                # 关键：提供formatter，把内容块合并为字符串，避免content是列表
                "formatter": formatter,
            },
            agent_builder=ReActAgent,
        )
