"""
考试题目验证系统数据模型

本模块定义了系统中使用的所有数据模型，包括：
- 内部业务模型：ExamQuestion, VerificationResult
- API 请求模型：ExamQuestionRequest, VerificationResultRequest, FixRequest, VerifyAndFixRequest
- API 响应模型：StandardResponse
- 枚举类型：QuestionType
"""

from typing import Optional, Literal, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator


# ---------- 枚举类型定义 ----------
class QuestionType(str, Enum):
    """考试题目类型枚举"""
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    FILL_BLANK = "fill_blank"
    BRIEF_ANSWER = "brief_answer"
    CALCULATION = "calculation"

    # 中文别名（保持向后兼容）
    单选题 = "single_choice"
    多选题 = "multi_choice"
    填空题 = "fill_blank"
    简答题 = "brief_answer"
    计算题 = "calculation"


# ---------- 内部业务模型 ----------
class ExamQuestion(BaseModel):
    """考试题目信息（内部业务模型）"""
    question: str = Field(description="考试题目")
    answer: str = Field(description="考试题目答案")
    question_type: str = Field(description="考试题目类型")
    knowledge_point: str = Field(description="考试题目所属的知识点")
    knowledge_point_description: str = Field(description="考试题目所属的知识点的具体描述")
    extra_requirement: str = Field(description="考试题目额外要求")


class VerificationResult(BaseModel):
    """考试题目核查结果（内部业务模型）"""
    is_compliant: bool = Field(description="考试题目是否合规")
    suggestion: str = Field(description="如果考试题目不合规，给出修正意见")


# ---------- API 请求模型 ----------
class ExamQuestionRequest(BaseModel):
    """考题请求体校验模型（API层）"""
    question: str = Field(..., min_length=5, description="考试题目，至少5个字符")
    answer: str = Field(..., min_length=1, description="考试题目答案")
    question_type: Union[QuestionType, str] = Field(
        ..., description="考试题目类型，支持英文或中文"
    )
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
        """自动去除字符串首尾空白字符"""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("question_type", mode="before")
    def normalize_question_type(cls, v):
        """标准化题目类型为英文枚举值"""
        if isinstance(v, QuestionType):
            return v
        if isinstance(v, str):
            # 直接匹配中文枚举
            for item in QuestionType:
                if item.value == v or item.name == v:
                    return item
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "请简述BFS和DFS搜索算法的区别",
                "answer": "BFS按层扩展，使用队列；DFS深度优先，使用栈或递归...",
                "question_type": "简答题",
                "knowledge_point": "图搜索算法",
                "knowledge_point_description": "DFS/BFS基础与最短路径问题",
                "extra_requirement": "表达清晰，分点说明",
            }
        }
    }


class VerificationResultRequest(BaseModel):
    """验证结果请求模型（API层）"""
    is_compliant: bool = Field(..., description="考试题目是否合规")
    suggestion: Optional[str] = Field(default=None, description="修正意见")


class FixRequest(BaseModel):
    """修复请求模型（API层）"""
    exam_question: ExamQuestionRequest
    verification_result: VerificationResultRequest

    model_config = {
        "json_schema_extra": {
            "example": {
                "exam_question": {
                    "question": "请简述BFS和DFS搜索算法的区别",
                    "answer": "BFS按层扩展，使用队列；DFS深度优先，使用栈或递归...",
                    "question_type": "简答题",
                    "knowledge_point": "图搜索算法",
                    "knowledge_point_description": "DFS/BFS基础与最短路径问题",
                    "extra_requirement": "表达清晰，分点说明",
                },
                "verification_result": {
                    "is_compliant": False,
                    "suggestion": "题干过长且不够明确，请拆分并增加约束。",
                },
            }
        }
    }


class VerifyAndFixRequest(BaseModel):
    """验证并修复请求模型（API层）"""
    exam_question: ExamQuestionRequest
    max_fix_attempts: int = Field(
        default=3, ge=1, le=5, description="最大修正次数，范围1-5"
    )


# ---------- API 响应模型 ----------
class StandardResponse(BaseModel):
    """标准响应模型（API层）"""
    code: int = Field(..., description="0表示成功，非0表示错误码")
    message: str = Field(..., description="状态说明")
    data: Optional[dict] = Field(default=None, description="返回数据")

    @property
    def is_success(self) -> bool:
        """便捷方法：检查请求是否成功"""
        return self.code == 0


class VerificationResponse(BaseModel):
    """验证结果响应模型（API层）"""
    question: str = Field(..., description="考试题目")
    answer: str = Field(..., description="考试题目答案")
    question_type: str = Field(..., description="考试题目类型")
    knowledge_point: Optional[str] = Field(..., description="考试题目所属的知识点")
    knowledge_point_description: Optional[str] = Field(..., description="考试题目所属的知识点的具体描述")
    extra_requirement: Optional[str] = Field(..., description="考试题目额外要求")
    is_compliant: bool = Field(..., description="是否合规")
    suggestion: Optional[str] = Field(default=None, description="修正意见")


# ---------- 导出列表 ----------
__all__ = [
    # 枚举类型
    "QuestionType",
    # 内部业务模型
    "ExamQuestion",
    "VerificationResult",
    # API 请求模型
    "ExamQuestionRequest",
    "VerificationResultRequest",
    "FixRequest",
    "VerifyAndFixRequest",
    # API 响应模型
    "StandardResponse",
    "VerificationResponse",
]