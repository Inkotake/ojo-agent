#!/bin/bash
# OJO v9.0 数据恢复脚本

set -e

if [ -z "$1" ]; then
    echo "用法: $0 <备份目录>"
    echo "示例: $0 ./backup/20241225_120000"
    exit 1
fi

BACKUP_DIR="$1"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "错误: 备份目录不存在: $BACKUP_DIR"
    exit 1
fi

echo "=========================================="
echo "  OJO v9.0 数据恢复"
echo "=========================================="
echo "备份目录: $BACKUP_DIR"
echo ""
echo "⚠️  警告: 此操作将覆盖现有数据！"
read -p "确认继续? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "已取消"
    exit 0
fi

# 停止服务
echo "[1/4] 停止服务..."
docker-compose down

# 恢复数据库卷
echo "[2/4] 恢复数据库卷..."
if [ -f "$BACKUP_DIR/ojo-data.tar.gz" ]; then
    # 确保卷存在
    docker volume create ojo-data 2>/dev/null || true
    
    docker run --rm \
        -v ojo-data:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine sh -c "rm -rf /data/* && tar xzf /backup/ojo-data.tar.gz -C /data"
    echo "  ✓ 数据库恢复完成"
else
    echo "  ⚠ 未找到数据库备份文件"
fi

# 恢复工作区卷
echo "[3/4] 恢复工作区卷..."
if [ -f "$BACKUP_DIR/ojo-workspace.tar.gz" ]; then
    docker volume create ojo-workspace 2>/dev/null || true
    
    docker run --rm \
        -v ojo-workspace:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine sh -c "rm -rf /data/* && tar xzf /backup/ojo-workspace.tar.gz -C /data"
    echo "  ✓ 工作区恢复完成"
else
    echo "  ⚠ 未找到工作区备份文件"
fi

# 恢复日志卷（可选）
echo "[4/4] 恢复日志卷..."
if [ -f "$BACKUP_DIR/ojo-logs.tar.gz" ]; then
    docker volume create ojo-logs 2>/dev/null || true
    
    docker run --rm \
        -v ojo-logs:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine sh -c "rm -rf /data/* && tar xzf /backup/ojo-logs.tar.gz -C /data"
    echo "  ✓ 日志恢复完成"
else
    echo "  ⚠ 未找到日志备份文件（可选）"
fi

# 启动服务
echo ""
echo "启动服务..."
docker-compose up -d

echo ""
echo "=========================================="
echo "  恢复完成！"
echo "=========================================="
echo "查看日志: docker-compose logs -f ojo-api"
echo "检查状态: docker-compose ps"
echo ""

