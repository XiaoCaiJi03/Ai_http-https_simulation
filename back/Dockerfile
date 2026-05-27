# ========== 阶段1：构建依赖（仅处理Python依赖） ==========
FROM python:3.11-slim AS builder

# 核心环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai \
    CRYPTOGRAPHY_DONT_BUILD_RUST=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    CFLAGS="-O0" \
    CXXFLAGS="-O0"

# 替换阿里云源（加速国内下载）
RUN rm -rf /etc/apt/sources.list /etc/apt/sources.list.d/* \
    && echo "deb http://mirrors.aliyun.com/debian trixie main contrib non-free" > /etc/apt/sources.list \
    && echo "deb http://mirrors.aliyun.com/debian-security trixie-security main contrib non-free" >> /etc/apt/sources.list

# 仅安装Python编译依赖（最小化构建）
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl bash \
        gcc python3-dev libffi-dev libssl-dev \
        libopenblas0 liblapack3 libblas3 \
        libnss3 ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 应用目录初始化
RUN mkdir -p /app \
    && chmod 755 -R /app && chown -R 1000:1000 /app

WORKDIR /app

# ========== 关键修正：Dockerfile 就在 back/ 下，直接复制当前目录 ==========
# 你的 Dockerfile 和 app.py 都在 back/ 目录，所以 COPY . 就是复制 back/ 下所有代码
COPY . /app/

# 安装Python依赖（此时 requirements.txt 已在 /app 目录）
RUN pip3 install --upgrade pip setuptools wheel \
    && pip3 install -i https://mirrors.aliyun.com/pypi/simple/ \
        --no-cache-dir \
        -r requirements.txt \
    && rm -rf ~/.cache/pip /tmp/*

# ========== 阶段2：运行镜像（永久配置tshark/权限/用户） ==========
FROM python:3.11-slim AS runner

# 运行时环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    RUNNING_IN_DOCKER=true \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=60110 \
    PYTHONUNBUFFERED=1

# 替换阿里云源
RUN rm -rf /etc/apt/sources.list /etc/apt/sources.list.d/* \
    && echo "deb http://mirrors.aliyun.com/debian trixie main contrib non-free" > /etc/apt/sources.list \
    && echo "deb http://mirrors.aliyun.com/debian-security trixie-security main contrib non-free" >> /etc/apt/sources.list

# 核心：安装tshark + 永久配置所有权限（无报错版本）
RUN apt-get update && apt-get install -y --no-install-recommends \
        tshark \
        net-tools iproute2 libcap2-bin \
        libopenblas0 libgomp1 libnss3 bash libffi8 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && which tshark || (echo "tshark install failed!" && exit 1) \
    && chmod +s /usr/bin/dumpcap \
    && groupadd -r wireshark || true \
    && useradd -m -u 1000 appuser -s /bin/bash -d /app -G wireshark

# 复制Python依赖和完整应用代码（从builder阶段）
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /app /app

# 配置应用目录权限（确保appuser可读写）
RUN chown -R appuser:appuser /app && rm -rf /tmp/*

# 切换到普通用户运行（安全最佳实践）
USER appuser

# 暴露端口
EXPOSE 60110 4433

# 启动应用（路径正确：/app/app.py）
CMD ["python", "/app/app.py"]