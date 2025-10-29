### Introduction
这里实现了考试问题核查功能

### 代码结构
- `exam_question_verification.py`：考试问题核查的实现代码
- `prompts.py`：考试问题核查的提示词
- `eqv_agent.py`：考试问题核查的agent代码
- `conf.yaml`：配置文件
- `schemas.py`：考试问题核查的API服务端代码中使用的请求和响应模型
- `fastapi_server.py`：考试问题核查的API服务端代码
- `agent_runtime.py`：考试问题核查agent的runtime代码

### 考试问题核查流程
1. 输入待核查的考题信息，考题信息包括：
    - 考题内容
    - 考题答案
    - 考题类型（如：单选题、多选题、填空题、简答题和计算题等）
    - 考题对应知识点
    - 考题对应知识点的详细描述
    - 用户对于考题的额外要求
2. 核查考题内容是否符合考题信息中的要求，若不符合，则输出考题内容修改建议，并执行3；反之退出核查流程
3. 根据2中输出的考题内容修改建议，修改考题内容，并输出修改后的考题信息
4. 执行2

### agent docker 部署
#### 准备 sandbox 镜像
```bash
# 基础镜像
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-base:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-base:latest agentscope/runtime-sandbox-base:latest

# GUI镜像
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-gui:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-gui:latest agentscope/runtime-sandbox-gui:latest

# 文件系统镜像
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-filesystem:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-filesystem:latest agentscope/runtime-sandbox-filesystem:latest

# 浏览器镜像
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest agentscope/runtime-sandbox-browser:latest
```

#### 一键部署考题核查容器
```bash
docker-compose up -d --build
```

#### 访问 API 服务
- 访问地址：`http://主机IP:8762`

#### 修改 API 服务接口
同时修改以下文件中的端口号为新的端口号
1. .env
    - `AGENT_RUNTIME_PORT`: 考试问题核查agent的runtime端口，默认值为8762
2. docker-compose.yml
    - `exam_question_verification.ports`: 考试问题核查agent的runtime端口映射，默认值为8762:8762
