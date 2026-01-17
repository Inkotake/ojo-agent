#!/bin/bash
# OJO v9.0 数据备份脚本

set -e

BACKUP_DIR="./backup/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "=========================================="
echo "  OJO v9.0 数据备份"
echo "=========================================="
echo "备份目录: $BACKUP_DIR"
echo ""

# 检查数据卷是否存在
echo "[1/4] 检查数据卷..."
if ! docker volume ls | grep -q ojo-data; then
    echo "  ⚠ 未找到 ojo-data 卷"
else
    echo "  ✓ 找到 ojo-data 卷"
fi

# 备份数据库卷
echo "[2/4] 备份数据库卷 (ojo-data)..."
if docker volume ls | grep -q ojo-data; then
    docker run --rm \
        -v ojo-data:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine tar czf /backup/ojo-data.tar.gz -C /data .
    echo "  ✓ 数据库备份完成"
else
    echo "  ⚠ 跳过（卷不存在）"
fi

# 备份工作区卷
echo "[3/4] 备份工作区卷 (ojo-workspace)..."
if docker volume ls | grep -q ojo-workspace; then
    docker run --rm \
        -v ojo-workspace:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine tar czf /backup/ojo-workspace.tar.gz -C /data .
    echo "  ✓ 工作区备份完成"
else
    echo "  ⚠ 跳过（卷不存在）"
fi

# 备份日志卷（可选）
echo "[4/4] 备份日志卷 (ojo-logs)..."
if docker volume ls | grep -q ojo-logs; then
    docker run --rm \
        -v ojo-logs:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine tar czf /backup/ojo-logs.tar.gz -C /data .
    echo "  ✓ 日志备份完成"
else
    echo "  ⚠ 跳过（卷不存在）"
fi

# 显示备份信息
echo ""
echo "=========================================="
echo "  备份完成！"
echo "=========================================="
echo "备份位置: $BACKUP_DIR"
echo ""
ls -lh "$BACKUP_DIR"
echo ""
echo "恢复命令:"
echo "  ./scripts/restore-data.sh $BACKUP_DIR"
echo ""

