# Runtime Sandbox Server Docker 容器

本Docker容器用于启动和管理宿主机中的沙箱容器，基于 `agentscope_runtime` 包构建。

## TODO
- [ ] 配置 `Redis` 为沙箱状态和状态管理提供缓存

## 构建容器

```bash
docker build -t runtime-sandbox-server .
```

## 运行容器

### 方法1：使用Docker命令直接运行

```bash
docker run -d --name sandbox-server \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -p 8010:8010 \
  runtime-sandbox-server
```

### 方法2：使用Docker Compose（推荐）

```bash
docker-compose up -d
```

# 文件结构说明

runtime_sandbox_server/
├── `conf.env`: 沙箱服务器配置文件
├── `delete_sandbox.sh `: 删除所有沙箱容器的脚本
├── `docker-compose.yml`: Docker Compose配置文件
└── `Dockerfile`: Dockerfile文件

## 容器功能

1. 基于 Python 3.10-slim 构建
2. 使用阿里云镜像源安装依赖，提升国内安装速度
3. 安装 `agentscope_runtime` 最新版本
4. 自动启动沙箱服务器，监听 8010 端口
5. 通过挂载Docker socket访问宿主机Docker守护进程

## 重要说明

- **Docker Socket挂载**: 容器需要访问宿主的Docker socket以管理沙箱容器，因此必须挂载 `/var/run/docker.sock`
- **端口映射**: 默认监听8010端口，可通过 `conf.env` 文件修改
- **容器管理**: 使用 `docker-compose` 可以更方便地管理容器生命周期

## 停止容器

```bash
# Docker方式
docker stop sandbox-server

# Docker Compose方式
docker-compose down

# (可选)为了防止容器关闭时，沙箱容器无法全部关闭并删除，因此推荐运行delete_sandbox.sh脚本完全删除沙箱容器
./delete_sandbox.sh
```

## 容器特性

- 自动重启策略（restart: unless-stopped）
- 通过环境变量配置（HOST、PORT等）
- 完整的日志输出
