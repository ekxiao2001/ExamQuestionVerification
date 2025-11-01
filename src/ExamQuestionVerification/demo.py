import os
import json
import requests
import asyncio
from pydantic import BaseModel, Field
from typing import Optional

from schemas import ExamQuestion

exam_question = ExamQuestion(
    question='''
    搜索算法相关\n（1）分别说明 DFS 和 BFS 如何用队列或栈实现，并对比两者遍历同一图时的顺序差异。\n（2）在求解无权图最短路径问题时，为什么 BFS 通常比 DFS 更高效？结合遍历特性解释原因。
    ''',
    answer="（1）DFS 用栈（递归或显式栈），一路深入再回溯；BFS 用队列，一层层扩展；顺序差异：DFS 纵深，BFS 横扩。\n（2）BFS 按层扩展，首次到达目标即最短路径；DFS 可能深入很长非最短路径才回溯，访问节点更多。",
    question_type="简答题",
    knowledge_point="",
    knowledge_point_description="",
    extra_requirement="将简答题修改为单选题",
)

text = '''
核查并修正考试题目:
考试题目：{question}
考题答案：{answer}
考试题目类型：{question_type}
考试题目所属的知识点：{knowledge_point}
考试题目所属的知识点的具体描述：{knowledge_point_description}
考试题目额外要求：{extra_requirement}
'''
inputs = text.format(**exam_question.model_dump())

def test_deployed_agent():
    # 准备测试负载
    payload = {
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": inputs},
                ],
            },
        ],
        "session_id": "test_session_002",
        "user_id": "test_user_002",
    }

    print("🧪 测试部署的智能体...")

    # 测试流式响应
    try:
        response = requests.post(
            "http://localhost:8021/process",
            json=payload,
            stream=True,
            timeout=300,
        )

        print("📡 流式响应:")
        for line in response.iter_lines():
            if line:
                res_json = json.loads(line[6:])
                # print(res_json["object"])
                # break
                if res_json["object"] == "message" and res_json["status"] == "completed":
                    content = res_json["content"][0]
                    if content:
                        if content["type"] == "text":
                            print(json.dumps(content["text"], ensure_ascii=False, indent=2))
                        elif content["type"] == "data":
                            print(json.dumps(content["data"], ensure_ascii=False, indent=2))
        print("✅ 流式测试完成")
    except requests.exceptions.RequestException as e:
        print(f"❌ 流式测试失败: {e}")


# Run the test
test_deployed_agent()