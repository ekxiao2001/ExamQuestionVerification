#!/bin/bash

# ====================
# 删除所有以 agent-runtime-container- 开头的容器
# ====================
# 定义前缀，对应 conf.env 中的 CONTAINER_PREFIX_KEY
PREFIX="agent-runtime-container-"
# 获取所有匹配的容器 ID
CONTAINER_IDS=$(docker ps -a | grep "^$PREFIX" | awk '{print $1}')
# 停止并删除容器
if [ -n "$CONTAINER_IDS" ]; then
    echo "停止容器: $CONTAINER_IDS"
    docker stop $CONTAINER_IDS

    echo "删除容器: $CONTAINER_IDS"
    docker rm $CONTAINER_IDS
else
    echo "没有找到前缀为 $PREFIX 的容器"
fi