import os
import uvicorn

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from exam_question_verification import build_exam_verifier
from schemas import (
    ExamQuestion,
    VerificationResult,
    ExamQuestionRequest,
    VerificationResultRequest,
    FixRequest,
    VerifyAndFixRequest,
    StandardResponse,
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


# ---------------------------
# 加载配置文件
# ---------------------------
import yaml
conf_path = os.path.join(os.path.dirname(__file__), "conf.yaml")
with open(conf_path, "r", encoding="utf-8") as f:
    CONF = yaml.safe_load(f)


# ---------- 业务初始化 ----------
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
        res: VerificationResult = await verifier.verify_exam_question(eq)
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
        new_eq: ExamQuestion = await verifier.fix_exam_question(eq, ver)
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
        final_eq: ExamQuestion = await verifier.verify_and_fix_exam_question(
            eq, max_fix_attempts=payload.max_fix_attempts
        )
        return StandardResponse(code=0, message="ok", data=final_eq.model_dump())
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"核查+修复失败: {e}", "data": None},
        )


if __name__ == "__main__":
    host = CONF.get("API_SERVER_HOST") or os.getenv("API_SERVER_HOST", "0.0.0.0")
    port = int(CONF.get("API_SERVER_PORT") or os.getenv("API_SERVER_PORT", "8000"))

    uvicorn.run(
        "fastapi_server:app",
        host=host,
        port=port,
        reload=True,
    )