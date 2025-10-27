import os
import asyncio
import logging
from typing import Any, Optional
from contextlib import asynccontextmanager
import socket
import concurrent.futures

from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.schemas.agent_schemas import (
    MessageType,
    RunStatus,
    AgentRequest,
)
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.deployers import LocalDeployManager
from agentscope_runtime.sandbox.tools.function_tool import FunctionTool, function_tool

from agentscope.model import OpenAIChatModel, DashScopeChatModel
from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit, ToolResponse
from agentscope.memory import InMemoryMemory
from agentscope.formatter import DeepSeekChatFormatter, DashScopeChatFormatter

from src.exam_question_verification import (
    ExamQuestionVerification, ExamQuestion, VerificationResult
)
from src.prompts import PROMPTS


# ---------------------------
# Logging
# ---------------------------
logger = logging.getLogger("agentscope_runtime")
logger.setLevel(logging.INFO)


# ---------------------------
# 环境变量加载
# ---------------------------
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
from dotenv import load_dotenv
load_dotenv(ENV_PATH)

# def load_env_from_file(dotenv_path: str) -> None:
#     try:
#         if os.path.isfile(dotenv_path):
#             with open(dotenv_path, "r", encoding="utf-8") as f:
#                 for line in f:
#                     line = line.strip()
#                     if not line or line.startswith("#"):
#                         continue
#                     if "=" not in line:
#                         continue
#                     key, value = line.split("=", 1)
#                     key = key.strip()
#                     value = value.strip().strip('"').strip("'")
#                     os.environ.setdefault(key, value)
#     except Exception as e:
#         raise RuntimeError(f".env 加载失败: {e}")

# load_env_from_file(ENV_PATH)


# 采用环境变量配置，移除 _cfg_get 辅助函数


def _build_exam_verifier() -> ExamQuestionVerification:
    """构建轻量的考试题目核查+修正器实例（工具内部使用）。"""
    llm_binding = os.getenv("LLM_BINDING", "deepseek")
    model_name = os.getenv("MODEL_NAME", "deepseek-chat")
    api_key = os.getenv("API_KEY", "")
    base_url = os.getenv("BASE_URL", "https://api.deepseek.com")

    if llm_binding == "deepseek":
        model = OpenAIChatModel(
            model_name=model_name,
            api_key=api_key,
            client_args={"base_url": base_url},
            stream=False,
        )
        formatter = DeepSeekChatFormatter()
    elif llm_binding == "dashscope":
        model = DashScopeChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=False,
        )
        formatter = DashScopeChatFormatter()
    else:
        raise ValueError(f"不支持的LLM绑定: {llm_binding}")

    return ExamQuestionVerification(model=model, formatter=formatter)


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
    verifier = _build_exam_verifier()
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
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
    verifier = _build_exam_verifier()
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_fix)
        new_eq = future.result()

    return new_eq.model_dump()

async def create_exam_question_verification_agent() -> AgentScopeAgent:
    """创建考试问题核查智能体。"""
    llm_binding = os.getenv("LLM_BINDING", "deepseek")
    model_name = os.getenv("MODEL_NAME", "deepseek-chat")
    api_key = os.getenv("API_KEY", "")
    base_url = os.getenv("BASE_URL", "https://api.deepseek.com")
    max_fix_attempts = int(os.getenv("MAX_FIX_ATTEMPTS", "3"))

    # 主代理用流式模型，支持异步迭代输出
    if llm_binding == "deepseek":
        model = OpenAIChatModel(
            model_name=model_name,
            api_key=api_key,
            client_args={"base_url": base_url},
            stream=True,
        )
        formatter = DeepSeekChatFormatter()
    elif llm_binding == "dashscope":
        model = DashScopeChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=True,
        )
        formatter = DashScopeChatFormatter()
    else:
        raise ValueError(f"不支持的LLM绑定: {llm_binding}")

    tools = [
        verify_exam_question_tool,
        fix_exam_question_tool,
    ]
    # print(json.dumps(verify_exam_question_tool.schema, ensure_ascii=False, indent=4))
    # print(json.dumps(fix_exam_question_tool.schema, ensure_ascii=False, indent=4))

    return AgentScopeAgent(
        name="exam_question_verification_agent",
        model=model,
        tools=tools,
        agent_config={
            "sys_prompt": PROMPTS["agent_sys_prompt"].format(max_fix_attempts=max_fix_attempts),
            # 关键：提供formatter，把内容块合并为字符串，避免content是列表
            "formatter": formatter,
        },
        agent_builder=ReActAgent,
    )



from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

from agentscope_runtime.engine.services.environment_manager import EnvironmentManager
from agentscope_runtime.engine.services.sandbox_service import SandboxService

@asynccontextmanager
async def create_runner(agent: AgentScopeAgent):
    # 创建Runner实例，绑定上下文管理器
    sandbox_host = "runtime_sandbox_base"
    sandbox_port = int(os.getenv("AGENT_RUNTIME_SANDBOX_PORT", "8002"))
    sandbox_url = f"http://{sandbox_host}:{sandbox_port}"
    async with Runner(
        agent=agent,
        context_manager=ContextManager(
            session_history_service=InMemorySessionHistoryService(),
            memory_service=InMemoryMemoryService(),
        ),
        environment_manager=EnvironmentManager(
            sandbox_service=SandboxService(
                base_url=sandbox_url,
            ),
        ),
    ) as runner:
        yield runner

def _get_accessible_host(conf_host: str) -> str:
    try:
        if conf_host in ("0.0.0.0", "", None):
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
        return conf_host
    except Exception:
        return "127.0.0.1"

async def deploy(runner: Runner):
    host_conf = os.getenv("AGENT_RUNTIME_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_RUNTIME_PORT", "8001"))
    endpoint_path = os.getenv("AGENT_RUNTIME_ENDPOINT_PATH", "")

    accessible_host = _get_accessible_host(host_conf)

    deploy_manager = LocalDeployManager(
        host=host_conf,
        port=port,
    )
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path=endpoint_path,
        stream=True,
    )

    logger.info(f"🚀智能体部署在: {deploy_result}")
    logger.info(f"🌐服务URL: http://{accessible_host}:{port}")
    logger.info(f"💚 健康检查: http://{accessible_host}:{port}/health")


async def _main() -> None:
    # 创建考试问题核查智能体
    agent = await create_exam_question_verification_agent()
    logger.info("✅ AgentScope agent created successfully")

    # 部署智能体为流式服务
    async with create_runner(agent=agent) as runner:
        await deploy(runner)
        # Keep the service running
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_main())

