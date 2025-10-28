import os
import yaml
import uvicorn
from typing import Optional, Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from src.exam_question_verification import (
    ExamQuestionVerification,
    ExamQuestion,
    VerificationResult,
)
from agentscope.formatter import (
    DeepSeekChatFormatter, 
    DashScopeChatFormatter,
)
from agentscope.model import (
    OpenAIChatModel, 
    DashScopeChatModel,
)


app = FastAPI(
    title="ExamQuestionVerification API",
    description=(
        "考试题目核查与修复服务。提供核查、修复、核查+修复三个端点。"
        "通过内置文档(/docs,/redoc)查看请求/响应示例与说明。"
    ),
    version="1.0.0",
)

# 允许局域网内其他设备访问与浏览器跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 请求与响应模型 ----------
class ExamQuestionRequest(BaseModel):
    """考题请求体校验模型"""
    question: str = Field(..., min_length=5, description="考试题目，至少5个字符")
    answer: str = Field(..., min_length=1, description="考试题目答案")
    question_type: Literal[
        "single_choice",
        "multi_choice",
        "fill_blank",
        "brief_answer",
        "calculation",
        "单选题",
        "多选题",
        "填空题",
        "简答题",
        "计算题",
    ] = Field(..., description="考试题目类型")
    knowledge_point: Optional[str] = Field(
        default="", description="考试题目所属的知识点"
    )
    knowledge_point_description: Optional[str] = Field(
        default="", description="考试题目所属的知识点的具体描述"
    )
    extra_requirement: Optional[str] = Field(
        default="", description="考试题目额外要求"
    )

    @field_validator(
        "question", "answer", "knowledge_point", "knowledge_point_description", "extra_requirement",
        mode="before",
    )
    def strip_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "搜索算法相关…",
                "answer": "BFS按层扩展…",
                "question_type": "简答题",
                "knowledge_point": "图搜索",
                "knowledge_point_description": "DFS/BFS基础与最短路径",
                "extra_requirement": "表达清晰，分点说明",
            }
        }
    }


class VerificationResultRequest(BaseModel):
    Compliance: bool = Field(..., description="考试题目是否合规")
    suggestion: Optional[str] = Field(default=None, description="修正意见")


class FixRequest(BaseModel):
    exam_question: ExamQuestionRequest
    verification_result: VerificationResultRequest

    model_config = {
        "json_schema_extra": {
            "example": {
                "exam_question": ExamQuestionRequest.model_json_schema()["example"],
                "verification_result": {
                    "Compliance": False,
                    "suggestion": "题干过长且不够明确，请拆分并增加约束。",
                },
            }
        }
    }


class VerifyAndFixRequest(BaseModel):
    exam_question: ExamQuestionRequest
    max_fix_attempts: int = Field(
        default=3, ge=1, le=5, description="最大修正次数(1-5)"
    )


class StandardResponse(BaseModel):
    code: int = Field(..., description="0表示成功，非0表示错误码")
    message: str = Field(..., description="状态说明")
    data: Optional[dict] = Field(default=None, description="返回数据")


# ---------- 加载 .env 配置到环境变量 ----------
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(ENV_PATH):
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


# ---------- 业务初始化 ----------
def build_verifier() -> ExamQuestionVerification:
    try:
        llm_binding = os.getenv("LLM_BINDING", "deepseek")
        model_name = os.getenv("MODEL_NAME", "deepseek-chat")
        api_key = os.getenv("API_KEY", "")
        base_url = os.getenv("BASE_URL", "https://api.deepseek.com")

        if llm_binding == "deepseek":
            formatter = DeepSeekChatFormatter()
            model = OpenAIChatModel(
                model_name=model_name,
                api_key=api_key,
                stream=False,
                client_args={"base_url": base_url},
            )
        elif llm_binding == "dashscope":
            formatter = DashScopeChatFormatter()
            model = DashScopeChatModel(
                model_name=model_name,
                api_key=api_key,
                stream=False,
            )
        else:
            raise ValueError(f"不支持的LLM绑定: {llm_binding}")

        return ExamQuestionVerification(
            formatter=formatter,
            model=model
        )
    except Exception as e:
        raise RuntimeError(f"加载模型失败: {e}")


exam_verifier = build_verifier()


# ---------- 健康检查 ----------
@app.get("/", summary="欢迎页")
async def root():
    return {
        "code": 0,
        "message": "ExamQuestionVerification API 服务运行中。访问 /docs 查看交互文档。",
        "data": None,
    }


@app.get("/health", summary="健康检查")
async def health():
    return {"code": 0, "message": "ok", "data": {"status": "healthy"}}


# ---------- 核心端点 ----------
@app.post(
    "/api/v1/verify",
    summary="考题核查",
    description="根据考题信息判断是否合规，并返回修正建议。",
    response_model=StandardResponse,
)
async def verify_endpoint(payload: ExamQuestionRequest):
    try:
        eq = ExamQuestion(**payload.model_dump())
        res: VerificationResult = await exam_verifier.verify_exam_question(eq)
        return StandardResponse(code=0, message="ok", data=res.model_dump())
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"核查失败: {e}", "data": None},
        )


@app.post(
    "/api/v1/fix",
    summary="考题修复",
    description="基于核查结果修复考题，返回修复后的考题信息。",
    response_model=StandardResponse,
)
async def fix_endpoint(payload: FixRequest):
    try:
        eq = ExamQuestion(**payload.exam_question.model_dump())
        ver = VerificationResult(**payload.verification_result.model_dump())
        new_eq: ExamQuestion = await exam_verifier.fix_exam_question(eq, ver)
        return StandardResponse(code=0, message="ok", data=new_eq.model_dump())
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"修复失败: {e}", "data": None},
        )


@app.post(
    "/api/v1/verify-and-fix",
    summary="考题核查并修复",
    description="先核查，必要时自动进行最多 max_fix_attempts 次修复，返回最终考题。",
    response_model=StandardResponse,
)
async def verify_and_fix_endpoint(payload: VerifyAndFixRequest):
    try:
        eq = ExamQuestion(**payload.exam_question.model_dump())
        final_eq: ExamQuestion = await exam_verifier.main(
            eq, max_fix_attempts=payload.max_fix_attempts
        )
        return StandardResponse(code=0, message="ok", data=final_eq.model_dump())
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"核查+修复失败: {e}", "data": None},
        )


if __name__ == "__main__":
    host = os.getenv("API_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("API_SERVER_PORT", "8000"))

    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=True,
    )