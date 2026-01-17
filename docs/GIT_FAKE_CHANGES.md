# Git 显示虚假修改问题

## 问题说明

Git 显示很多文件已修改（M），但实际上你没有修改过。这通常是因为：
- 文件换行符差异（Windows CRLF vs Linux LF）
- 文件权限变化
- Git 配置问题

## 快速解决

### 方案 1: 放弃所有"修改"（推荐）

```bash
cd /opt/ojo

# 放弃所有本地"修改"
git checkout -- .

# 或者使用 reset（更彻底）
git reset --hard HEAD

# 然后拉取最新代码
git fetch origin
git reset --hard origin/main
```

### 方案 2: 配置 Git 忽略换行符差异

```bash
cd /opt/ojo

# 配置 Git 自动处理换行符
git config core.autocrlf false
git config core.filemode false

# 然后重置
git reset --hard HEAD
git fetch origin
git reset --hard origin/main
```

### 方案 3: 强制重置到远程（最简单）

```bash
cd /opt/ojo

# 直接强制重置到远程版本
git fetch origin
git reset --hard origin/main

# 这会丢弃所有本地"修改"，使用远程版本
```

## 推荐操作

```bash
cd /opt/ojo

# 1. 配置 Git（避免以后出现）
git config core.autocrlf false
git config core.filemode false

# 2. 强制重置到远程
git fetch origin
git reset --hard origin/main

# 3. 验证
git status  # 应该显示 "working tree clean"

# 4. 继续操作
chmod +x scripts/*.sh
./scripts/update-from-registry.sh
```

---

**最简单**: `git fetch origin && git reset --hard origin/main`

