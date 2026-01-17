# Git 网络问题快速解决

## 问题：git pull/fetch 卡住

即使网络能 ping 通，Git 操作也可能因为超时或协议问题卡住。

## 🚀 最快解决方案

### 方案 1: 设置超时并强制重置（推荐）

```bash
cd /opt/ojo

# 1. 设置 Git 超时（避免无限等待）
git config --global http.postBuffer 524288000
git config --global http.lowSpeedLimit 0
git config --global http.lowSpeedTime 30

# 2. 使用 fetch 并设置超时
timeout 30 git fetch origin || true

# 3. 强制重置到远程版本
git reset --hard origin/main
```

### 方案 2: 直接下载 ZIP 文件（最快）

```bash
cd /opt

# 1. 备份当前代码和配置
cp -r ojo ojo-backup

# 2. 下载最新代码（ZIP）
wget https://github.com/Inkotake/ojo/archive/refs/heads/main.zip -O ojo-main.zip
unzip -o ojo-main.zip
rm ojo-main.zip

# 3. 替换代码（保留配置）
rm -rf ojo
mv ojo-main ojo

# 4. 恢复 .env 文件
cp ojo-backup/.env ojo/.env 2>/dev/null || true

# 5. 继续操作
cd ojo
chmod +x scripts/*.sh
```

### 方案 3: 使用 SSH（如果已配置 SSH key）

```bash
# 1. 切换到 SSH 地址
git remote set-url origin git@github.com:Inkotake/ojo.git

# 2. 拉取
git pull origin main
```

### 方案 4: 分步操作（避免卡住）

```bash
cd /opt/ojo

# 1. 只获取远程信息（不合并）
timeout 30 git fetch origin main --depth=1 || true

# 2. 如果成功，重置
git reset --hard origin/main

# 3. 如果还是卡住，使用方案 2（下载 ZIP）
```

## 🔧 临时解决方案

如果急需更新，可以手动复制文件：

```bash
# 在本地下载最新代码
# 然后通过 SCP 上传到服务器

# 在本地执行：
scp -r src/ root@your-server:/opt/ojo/
scp scripts/*.sh root@your-server:/opt/ojo/scripts/
```

## ⚡ 一键解决脚本

创建 `scripts/force-update.sh`:

```bash
#!/bin/bash
# 强制更新脚本

cd /opt/ojo

# 备份配置
cp .env .env.bak 2>/dev/null || true

# 下载最新代码
cd /opt
wget -q https://github.com/Inkotake/ojo/archive/refs/heads/main.zip -O ojo-update.zip
unzip -q -o ojo-update.zip
rm ojo-update.zip

# 替换代码
rm -rf ojo
mv ojo-main ojo

# 恢复配置
cp ojo/.env.bak ojo/.env 2>/dev/null || true

cd ojo
chmod +x scripts/*.sh

echo "更新完成！"
```

---

**推荐**: 使用方案 2（下载 ZIP），最快最可靠！

