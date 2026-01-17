# Git 冲突解决指南

## 问题说明

当服务器上的文件有本地修改，而远程也有更新时，Git 会提示冲突。

## 解决方案

### 方案 1: 保存本地修改（如果重要）

```bash
# 1. 查看本地修改
git diff scripts/update-from-registry.sh

# 2. 暂存本地修改
git stash

# 3. 拉取远程更新
git pull origin main

# 4. 恢复本地修改（如果需要）
git stash pop
```

### 方案 2: 放弃本地修改（推荐，使用远程版本）

```bash
# 1. 放弃本地修改，使用远程版本
git checkout -- scripts/update-from-registry.sh

# 2. 拉取远程更新
git pull origin main
```

### 方案 3: 强制使用远程版本（最简单）

```bash
# 1. 重置到远程版本（会丢失所有本地未提交的修改）
git fetch origin
git reset --hard origin/main
```

**⚠️ 注意**: 这会丢失所有本地未提交的修改！

### 方案 4: 提交本地修改后再拉取

```bash
# 1. 提交本地修改
git add scripts/update-from-registry.sh
git commit -m "本地修改"

# 2. 拉取并合并
git pull origin main

# 如果有冲突，解决后：
git add .
git commit -m "解决冲突"
```

## 推荐操作（服务器端）

对于服务器端，通常建议使用**方案 2**（放弃本地修改）：

```bash
cd /opt/ojo

# 放弃本地修改
git checkout -- scripts/update-from-registry.sh

# 拉取最新代码
git pull origin main

# 更新服务
./scripts/update-from-registry.sh
```

## 预防措施

### 1. 不要在服务器上直接修改代码

服务器上的代码应该只通过 `git pull` 更新，不要手动编辑。

### 2. 使用配置文件

如果需要自定义配置，使用 `.env` 文件，而不是修改脚本。

### 3. 定期更新

```bash
# 定期拉取更新
cd /opt/ojo
git pull origin main
```

---

**快速解决**: 执行 `git checkout -- scripts/update-from-registry.sh && git pull origin main`

