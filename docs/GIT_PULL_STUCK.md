# Git Pull 卡住问题解决

## 快速解决

### 1. 中断当前操作

```bash
# 按 Ctrl+C 中断（如果还没中断）
# 然后执行：
```

### 2. 检查网络连接

```bash
# 测试 GitHub 连接
ping github.com

# 或测试 Git 连接
git ls-remote origin
```

### 3. 使用强制拉取（推荐）

```bash
# 放弃本地修改，强制使用远程版本
git fetch origin
git reset --hard origin/main
```

### 4. 如果还是卡住，使用完整 URL

```bash
# 检查远程仓库地址
git remote -v

# 如果使用 HTTPS，可能需要配置凭据
# 或者切换到 SSH（如果已配置 SSH key）
```

## 详细解决方案

### 方案 1: 强制重置（最快）

```bash
cd /opt/ojo

# 1. 中断当前操作（Ctrl+C）

# 2. 强制重置到远程版本
git fetch origin
git reset --hard origin/main

# 3. 检查状态
git status
```

### 方案 2: 配置 Git 超时

```bash
# 设置更短的超时时间
git config --global http.postBuffer 524288000
git config --global http.lowSpeedLimit 0
git config --global http.lowSpeedTime 999999

# 然后重试
git pull origin main
```

### 方案 3: 使用 SSH（如果已配置）

```bash
# 检查远程地址
git remote -v

# 如果是 HTTPS，切换到 SSH
git remote set-url origin git@github.com:your-username/ojo.git

# 然后拉取
git pull origin main
```

### 方案 4: 手动下载并替换

如果 Git 一直有问题：

```bash
# 1. 备份当前代码
cd /opt
cp -r ojo ojo-backup

# 2. 删除并重新克隆
rm -rf ojo
git clone <repository-url> ojo
cd ojo

# 3. 恢复 .env 文件（从备份）
cp ../ojo-backup/.env .env

# 4. 继续操作
chmod +x scripts/*.sh
./scripts/update-from-registry.sh
```

## 预防措施

### 1. 配置 Git 凭据缓存

```bash
# 缓存凭据 1 小时
git config --global credential.helper 'cache --timeout=3600'
```

### 2. 使用 SSH Key（推荐）

```bash
# 生成 SSH key（如果没有）
ssh-keygen -t ed25519 -C "your_email@example.com"

# 添加到 GitHub
cat ~/.ssh/id_ed25519.pub
# 复制内容到 GitHub → Settings → SSH and GPG keys

# 切换远程地址
git remote set-url origin git@github.com:your-username/ojo.git
```

---

**最快解决**: `git fetch origin && git reset --hard origin/main`

