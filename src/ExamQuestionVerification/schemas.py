from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class ExamQuestion(BaseModel):
    """考试题目信息"""
    question: str = Field(description="考试题目")
    answer: str = Field(description="考试题目答案")
    question_type: str = Field(description="考试题目类型")
    knowledge_point: str = Field(description="考试题目所属的知识点")
    knowledge_point_description: str = Field(description="考试题目所属的知识点的具体描述")
    extra_requirement: Optional[str] = Field(description="考试题目额外要求")


class VerificationResult(BaseModel):
    """考试题目核查结果"""
    Compliance: bool = Field(description="考试题目是否合规")
    suggestion: Optional[str] = Field(description="如果考试题目不合规，给出修正意见")


# ---------- 请求与响应模型（API层使用） ----------
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


__all__ = [
    "ExamQuestion",
    "VerificationResult",
    "ExamQuestionRequest",
    "VerificationResultRequest",
    "FixRequest",
    "VerifyAndFixRequest",
    "StandardResponse",
]