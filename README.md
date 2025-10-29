## 快速开始
### 准备 sandbox 镜像
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

### 一键部署容器
```bash
docker-compose up -d --build
```
**Note**
初次启动时需要等待UV安装依赖，可能需要一些时间。

### API 服务
#### Exam Question Verification(考题核查+修正)
API 端口 配置文件路径： `src/ExamQuestionVerification/conf.yaml`
| 方法 | 默认访问路径 | 端口配置参数 |
| --- | --- | --- |
| agent_runtime | http://主机IP:8021 | AGENT_RUNTIME_PORT |
| fastapi_server | http://主机IP:8022 | API_SERVER_PORT |
1. agent_runtime: 考题核查+修正对话智能体，通过对话的形式修改考题。
    - POST /process: 对话接口
2. fastapi_server: 提供考题核查+修正的API服务，包括以下接口：
    - POST /api/v1/verify：接收用户输入的考题信息，返回核查结果。
    - POST /api/v1/fix：接收考题以及核查结果，返回修正考题。
    - POST /api/v1/verify-and-fix：接收用户输入的考题信息，一键核查+修复考题。