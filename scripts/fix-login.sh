#!/bin/bash
# 修复登录问题脚本
# 检查数据库、环境变量和服务状态

set -e

echo "=========================================="
echo "  OJO 登录问题诊断和修复"
echo "=========================================="
echo ""

# 检查服务状态
echo "[1/5] 检查服务状态..."
if docker ps | grep -q ojo-api; then
    echo "  ✓ 服务正在运行"
    CONTAINER_NAME=$(docker ps | grep ojo-api | awk '{print $1}')
else
    echo "  ✗ 服务未运行"
    echo "  请先启动服务: docker-compose up -d"
    exit 1
fi

# 检查数据卷
echo ""
echo "[2/5] 检查数据卷..."
if docker volume ls | grep -q ojo-data; then
    echo "  ✓ 数据卷存在"
    VOLUME_PATH=$(docker volume inspect ojo-data --format '{{ .Mountpoint }}')
    echo "  数据卷路径: $VOLUME_PATH"
else
    echo "  ✗ 数据卷不存在"
    echo "  这可能是新安装，将创建新的数据库"
fi

# 检查数据库文件
echo ""
echo "[3/5] 检查数据库文件..."
DB_FILE="/app/data/ojo.db"
if docker exec $CONTAINER_NAME test -f $DB_FILE 2>/dev/null; then
    echo "  ✓ 数据库文件存在: $DB_FILE"
    
    # 检查用户表
    USER_COUNT=$(docker exec $CONTAINER_NAME sqlite3 $DB_FILE "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0")
    echo "  用户数量: $USER_COUNT"
    
    if [ "$USER_COUNT" = "0" ]; then
        echo "  ⚠ 数据库中没有用户，需要创建默认用户"
    else
        echo "  用户列表:"
        docker exec $CONTAINER_NAME sqlite3 $DB_FILE "SELECT id, username, role, status FROM users;" 2>/dev/null || echo "  无法读取用户表"
    fi
else
    echo "  ✗ 数据库文件不存在"
    echo "  数据库将在服务启动时自动创建"
fi

# 检查环境变量
echo ""
echo "[4/5] 检查环境变量..."
JWT_SECRET=$(docker exec $CONTAINER_NAME printenv JWT_SECRET_KEY 2>/dev/null || echo "")
ENCRYPTION_KEY=$(docker exec $CONTAINER_NAME printenv OJO_ENCRYPTION_KEY 2>/dev/null || echo "")

if [ -z "$JWT_SECRET" ]; then
    echo "  ⚠ JWT_SECRET_KEY 未设置"
    echo "  这会导致无法验证 Token，需要重启服务"
else
    echo "  ✓ JWT_SECRET_KEY 已设置"
fi

if [ -z "$ENCRYPTION_KEY" ]; then
    echo "  ⚠ OJO_ENCRYPTION_KEY 未设置"
else
    echo "  ✓ OJO_ENCRYPTION_KEY 已设置"
fi

# 查看服务日志（查找默认密码）
echo ""
echo "[5/5] 查看服务日志（查找默认密码）..."
echo "  正在查看最近 100 行日志..."
echo ""
docker logs --tail 100 $CONTAINER_NAME 2>&1 | grep -i -E "(默认|default|password|密码|inkotake|首次运行)" || echo "  未找到默认密码信息"

echo ""
echo "=========================================="
echo "  诊断完成"
echo "=========================================="
echo ""
echo "可能的解决方案："
echo ""
echo "1. 如果数据库中没有用户："
echo "   - 查看服务日志找到默认密码"
echo "   - 或设置环境变量 OJO_ADMIN_PASSWORD 后重启服务"
echo ""
echo "2. 如果环境变量未设置："
echo "   - 编辑 .env 文件，添加："
echo "     JWT_SECRET_KEY=your-secret-key"
echo "     OJO_ENCRYPTION_KEY=your-encryption-key"
echo "   - 重启服务: docker-compose restart ojo-api"
echo ""
echo "3. 如果需要重置密码："
echo "   - 使用 Python 脚本直接修改数据库"
echo "   - 或删除数据库文件让系统重新创建"
echo ""
echo "4. 查看完整日志："
echo "   docker logs -f $CONTAINER_NAME"
echo ""


