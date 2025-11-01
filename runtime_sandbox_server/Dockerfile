# 构建沙箱启动专用容器
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 配置阿里云镜像源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 安装agentscope_runtime最新版本
RUN pip install --no-cache-dir agentscope_runtime

# 复制配置文件和启动脚本
COPY conf.env /app/

# 直接运行runtime-sandbox-server命令
CMD ["runtime-sandbox-server", "--config", "/app/conf.env"]
