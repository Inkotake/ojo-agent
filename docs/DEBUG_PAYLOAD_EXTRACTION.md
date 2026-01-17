# 从 Docker 容器获取调试 Payload 文件

## 步骤 1: SSH 连接到服务器

```bash
ssh user@your-server-ip
# 或使用密钥
ssh -i ~/.ssh/your_key user@your-server-ip
```

## 步骤 2: 找到 Docker 容器

```bash
# 查看运行中的容器
docker ps

# 或者查看所有容器（包括停止的）
docker ps -a

# 通常容器名可能包含 "ojo" 或相关关键词
# 例如：ojo_app, ojo-api, ojo-server 等
```

## 步骤 3: 进入容器查找调试文件

### 方法 A: 直接进入容器查找

```bash
# 进入容器（替换 CONTAINER_NAME 为实际容器名）
docker exec -it CONTAINER_NAME /bin/bash
# 或如果容器没有 bash，使用 sh
docker exec -it CONTAINER_NAME /bin/sh

# 在容器内查找调试文件
find /tmp -name "shsoj_debug_payload_*.json" -type f 2>/dev/null

# 或者直接查看最新的文件（按时间排序）
ls -lt /tmp/shsoj_debug_payload_*.json 2>/dev/null | head -1
```

### 方法 B: 从容器复制文件到宿主机

```bash
# 先找到文件路径（在容器内）
docker exec CONTAINER_NAME find /tmp -name "shsoj_debug_payload_*.json" -type f 2>/dev/null

# 复制文件到宿主机（替换 CONTAINER_NAME 和文件路径）
docker cp CONTAINER_NAME:/tmp/shsoj_debug_payload_19733.json ./shsoj_debug_payload_19733.json

# 查看文件内容
cat shsoj_debug_payload_19733.json
```

## 步骤 4: 获取文件内容

### 如果文件在容器内：

```bash
# 在容器内查看文件内容
cat /tmp/shsoj_debug_payload_19733.json

# 或者使用 less 查看（支持滚动）
less /tmp/shsoj_debug_payload_19733.json
```

### 如果已复制到宿主机：

```bash
# 查看文件内容
cat shsoj_debug_payload_19733.json

# 或者使用编辑器
nano shsoj_debug_payload_19733.json
# 或
vi shsoj_debug_payload_19733.json
```

## 步骤 5: 将内容传给我

你可以：
1. **直接复制粘贴**：在容器内或宿主机上 `cat` 文件，然后复制输出内容给我
2. **使用 scp 下载到本地**：
   ```bash
   # 在本地机器执行
   scp user@server-ip:/path/to/shsoj_debug_payload_19733.json ./
   ```
3. **使用 base64 编码传输**（如果文件很大）：
   ```bash
   # 在服务器上
   base64 /tmp/shsoj_debug_payload_19733.json
   # 然后复制输出给我，我可以解码
   ```

## 快速一键命令（如果知道容器名）

```bash
# 假设容器名是 ojo_app，题目ID是 19733
CONTAINER_NAME="ojo_app"  # 替换为实际容器名
PID="19733"  # 替换为实际题目ID

# 查找并显示文件内容
docker exec $CONTAINER_NAME cat /tmp/shsoj_debug_payload_${PID}.json

# 或者复制到宿主机
docker cp $CONTAINER_NAME:/tmp/shsoj_debug_payload_${PID}.json ./debug_payload.json
cat ./debug_payload.json
```

## 注意事项

1. **文件可能不存在**：如果错误发生在很久以前，临时文件可能已被清理
2. **权限问题**：如果遇到权限错误，可能需要使用 `sudo` 或确保用户有 Docker 权限
3. **多个文件**：如果有多个调试文件，选择最新的（按时间排序）

## 如果找不到文件

可以：
1. **查看容器日志**，找到保存文件的路径：
   ```bash
   docker logs CONTAINER_NAME | grep "已保存调试payload"
   ```
2. **检查其他可能的临时目录**：
   ```bash
   docker exec CONTAINER_NAME find / -name "shsoj_debug_payload_*.json" 2>/dev/null
   ```
3. **重新触发错误**，让系统再次保存调试文件

