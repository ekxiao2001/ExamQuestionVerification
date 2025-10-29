FROM python:3.10-slim

WORKDIR /app

# Configure apt to use domestic mirror for new Debian source format
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources
# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    vim \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# ----------
# 安装 Rust
# ----------
# 方法1. Install Rust using rustup with a domestic mirror for faster download
# RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal

# 方法2. 本地安装
# wget https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init
RUN --mount=type=cache,target=/tmp/rustup_cache \
    # 使用 bind mount 将构建上下文中的 rustup-init 文件挂载到容器内
    --mount=type=bind,source=rustup-init,target=/tmp/rustup_init_source \
    command -v rustc > /dev/null && echo "Rust already installed, skipping." || ( \
        echo "Installing Rust..." && \
        # 1. 从 bind mount 的源文件复制到可写的缓存目录
        cp /tmp/rustup_init_source /tmp/rustup_cache/rustup-init && \
        # 2. 后续操作都在缓存目录中进行
        chmod +x /tmp/rustup_cache/rustup-init && \
        /tmp/rustup_cache/rustup-init -y --profile minimal --default-toolchain none && \
        ln -s /root/.cargo/bin/rustup /usr/local/bin/rustup && \
        ln -s /root/.cargo/bin/cargo /usr/local/bin/cargo && \
        ln -s /root/.cargo/bin/rustc /usr/local/bin/rustc \
    )

ENV PATH="/root/.local/bin:${PATH}"
ENV PATH="/root/.cargo/bin:${PATH}"

# Configure uv to use domestic mirror
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# ----------
# 安装 uv
# ----------
# 方法1. Install uv using the installer script
# ADD https://astral.sh/uv/install.sh /uv-installer.sh
# RUN sh /uv-installer.sh && rm /uv-installer.sh

# 方法2. Install uv using pip from domestic mirror (alternative to installer script)
# RUN pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple uv

# 方法3. 本地安装。假设你已经把 tar.gz 文件复制到了项目根目录
# Release 页面: https://github.com/astral-sh/uv/releases
# 对于大多数 Linux 服务器（x86_64 架构），你需要下载 uv-x86_64-unknown-linux-musl.tar.gz 这样的文件
# --- 安装 uv (使用缓存优化，单步完成) ---
RUN --mount=type=cache,target=/tmp/uv_cache \
    # 使用 bind mount 将构建上下文中的 uv 压缩包挂载到容器内
    --mount=type=bind,source=uv-x86_64-unknown-linux-musl.tar.gz,target=/tmp/uv_source.tar.gz \
    command -v uv > /dev/null && echo "uv already installed, skipping." || ( \
        echo "Installing uv..." && \
        # 1. 从 bind mount 的源文件复制到可写的缓存目录
        cp /tmp/uv_source.tar.gz /tmp/uv_cache/uv.tar.gz && \
        # 2. 在缓存目录中解压
        tar -xzf /tmp/uv_cache/uv.tar.gz -C /tmp/uv_cache && \
        # 3. 从缓存目录将 uv 二进制文件移动到系统路径
        mv /tmp/uv_cache/uv-x86_64-unknown-linux-musl/uv /usr/local/bin/ \
    )

# Copy project files for dependency installation (better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies first (better layer caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Copy application code
COPY src/ ./src/
COPY .env ./

# Supervisor 配置
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN mkdir -p /var/log/supervisor

# Expose port
EXPOSE 8761 8762

# 使用 CMD 启动 Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]