# -*- coding: utf-8 -*-
"""HydroOJ数据上传实现"""

import json
import re
import shutil
import tempfile
import time
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List

from loguru import logger

from ...base.data_uploader import DataUploader


class HydroOJDataUploader(DataUploader):
    """HydroOJ 数据上传器"""
    
    def __init__(self, base_url: str, domain: str, preferred_prefix: str = ""):
        self.base_url = base_url.rstrip("/")
        self.domain = domain
        self.preferred_prefix = preferred_prefix
    
    def upload_testcase(self, problem_id: str, data_path: Path, auth: Any, skip_update: bool = False) -> Dict[str, Any]:
        """上传测试数据（Hydro格式）
        
        Args:
            problem_id: 题目ID（规范化ID）
            data_path: 数据路径（zip文件路径，虽然HydroOJ不直接使用）
            auth: HydroOJAuth 认证对象
            skip_update: 如果为True，跳过更新已存在题目，直接创建新题目
            
        Returns:
            上传结果
        """
        # 从 data_path 推断工作区目录
        # data_path 格式: workspace/user_{user_id}/problem_{problem_id}/xxx.zip
        data_path_obj = Path(data_path)
        workspace_dir = data_path_obj.parent  # zip 文件所在目录就是工作区
        
        problem_data_file = workspace_dir / "problem_data.json"
        
        if not problem_data_file.exists():
            raise FileNotFoundError(
                f"题面数据文件不存在: {problem_data_file}\n"
                f"提示: 请确保已执行'拉取题面'步骤，或检查题目ID是否正确。\n"
                f"对于手动输入的题目，请确保勾选'拉取题面'选项。"
            )
        
        with open(problem_data_file, 'r', encoding='utf-8') as f:
            problem_data = json.load(f)
        
        # 保存题目标题，用于后续搜索
        title = problem_data.get('title', '')
        self._last_upload_title = title
        
        # 测试数据目录（在搜索之前定义，更新时也需要使用）
        testdata_dir = workspace_dir / "tests"
        logger.debug(f"[HydroOJ Upload] 检查测试数据目录: {testdata_dir}")
        logger.debug(f"[HydroOJ Upload] 工作区目录存在: {workspace_dir.exists()}")
        logger.debug(f"[HydroOJ Upload] 测试数据目录存在: {testdata_dir.exists()}")
        
        if not testdata_dir.exists():
            # 列出工作区目录内容，便于诊断
            if workspace_dir.exists():
                contents = list(workspace_dir.iterdir())
                logger.error(f"[HydroOJ Upload] 工作区目录内容: {[p.name for p in contents]}")
            raise FileNotFoundError(
                f"测试数据目录不存在: {testdata_dir}\n"
                f"提示: 请确保已执行'生成数据'步骤。"
            )
        
        # 如果 skip_update=True，跳过搜索和更新，直接上传
        if skip_update:
            logger.info(f"[HydroOJ Upload] 跳过更新模式：直接创建新题目（不检查是否已存在）")
        else:
            # 搜索是否已存在同名题目
            existing_id = self._search_problem_by_title(title, auth)
            
            if existing_id:
                # ===== 严格验证：必须标题完全匹配才更新，避免错误覆盖其他题目 =====
                should_update = False
                try:
                    detail_url = f"{self.base_url}/d/{self.domain}/p/{existing_id}"
                    headers = {
                        'User-Agent': 'Mozilla/5.0',
                        'Referer': f"{self.base_url}/d/{self.domain}/p",
                    }
                    detail_r = auth.session.get(detail_url, headers=headers, timeout=30)
                    detail_r.raise_for_status()
                    
                    # 从页面中提取实际标题（在 <title> 或页面内容中）
                    # HydroOJ 页面标题格式通常是 "题目标题 - Domain - Hydro"
                    title_match = re.search(r'<title>([^<]+)</title>', detail_r.text)
                    if title_match:
                        page_title = title_match.group(1).split(' - ')[0].strip()
                        # 严格匹配：标题必须完全一致
                        if page_title == title.strip():
                            should_update = True
                            logger.info(f"[HydroOJ Upload] ✓ 标题完全匹配: '{page_title}'")
                        else:
                            logger.warning(f"[HydroOJ Upload] ✗ 标题不匹配: 本地='{title}', 远端='{page_title}'")
                    else:
                        logger.warning(f"[HydroOJ Upload] 无法提取远端题目标题，跳过更新")
                except Exception as e:
                    logger.warning(f"[HydroOJ Upload] 验证远端题目时出错: {e}，跳过更新")
                
                if should_update:
                    logger.info(f"[HydroOJ Upload] 找到已存在题目: {existing_id}，更新测试数据")
                    # 更新测试数据（而不是跳过）
                    try:
                        return self._update_testdata(existing_id, testdata_dir, auth)
                    except Exception as e:
                        logger.error(f"[HydroOJ Upload] 更新测试数据失败: {e}")
                        # 更新失败，记录错误但不创建新题目（避免重复）
                        raise RuntimeError(f"更新已存在题目 {existing_id} 失败: {e}")
                else:
                    # ===== 修复：标题不匹配时，再次精确搜索是否已有同名题目 =====
                    # 避免创建重复题目
                    exact_match_id = self._search_exact_title(title, auth)
                    if exact_match_id:
                        logger.info(f"[HydroOJ Upload] ✓ 找到精确匹配的题目 {exact_match_id}，跳过上传")
                        return {
                            "status": "success",
                            "code": 200,
                            "real_id": exact_match_id,
                            "message": f"题目已存在（ID: {exact_match_id}），跳过上传",
                            "skipped": True
                        }
                    logger.warning(f"[HydroOJ Upload] 搜索到题目 {existing_id} 但标题不完全匹配，将创建新题目（避免错误覆盖）")
        
        logger.info(f"[HydroOJ Upload] 题目不存在，创建新题目")
        # 打包为 Hydro 格式
        # 使用 sanitize_filename 处理 title，移除 Windows 不允许的字符（如引号）
        from utils.text import sanitize_filename
        safe_title = sanitize_filename(title)
        output_zip = workspace_dir / f"{safe_title}_hydro.zip"
        self._pack_hydro_zip(problem_data, testdata_dir, output_zip, problem_id)
        
        # 上传
        return self._upload_to_hydro(output_zip, auth)
    
    def supports_format(self, format_type: str) -> bool:
        """支持 zip 和 dir 格式"""
        return format_type.lower() in ['zip', 'dir']
    
    def _search_exact_title(self, title: str, auth: Any) -> Optional[str]:
        """精确标题匹配搜索（支持标题规范化）
        
        标题规范化规则：
        1. 去除首尾空格
        2. 将多个连续空格替换为单个空格
        3. 比较时忽略空格差异
        
        Args:
            title: 题目标题
            auth: HydroOJAuth 认证对象
            
        Returns:
            精确匹配的题目ID，未找到则返回 None
        """
        if not title:
            return None
        
        try:
            # 规范化标题：去除首尾空格，多个空格合并为一个
            normalized_title = ' '.join(title.strip().split())
            
            from urllib.parse import quote
            search_url = f"{self.base_url}/d/{self.domain}/p?q={quote(normalized_title)}"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Referer': f"{self.base_url}/d/{self.domain}/p",
            }
            r = auth.session.get(search_url, headers=headers, timeout=30)
            r.raise_for_status()
            
            problem_rows = re.finditer(
                r'<tr[^>]*data-pid="([^"]+)"[^>]*>(.*?)</tr>',
                r.text,
                re.DOTALL
            )
            
            for row_match in problem_rows:
                pid = row_match.group(1)
                row_html = row_match.group(2)
                
                title_match = re.search(r'<a[^>]*>([^<]+)</a>', row_html)
                if title_match:
                    # 规范化远端标题（同样处理空格）
                    found_title = ' '.join(title_match.group(1).strip().split())
                    if found_title == normalized_title:
                        logger.debug(f"[HydroOJ Upload] _search_exact_title 找到: {pid} (标题: '{found_title}')")
                        return pid
            
            logger.debug(f"[HydroOJ Upload] _search_exact_title 未找到匹配: '{normalized_title}'")
            return None
        except Exception as e:
            logger.debug(f"[HydroOJ Upload] _search_exact_title 失败: {e}")
            return None
    
    def _search_problem_by_title(self, title: str, auth: Any, tags: List[str] = None) -> Optional[str]:
        """通过题目标题搜索，返回题目ID（精确匹配优先）
        
        搜索策略：
        1. 优先精确标题匹配
        2. 如果有 tags，在精确匹配基础上进一步验证标签
        3. 不使用模糊匹配，避免返回错误题目
        
        Args:
            title: 题目标题
            auth: HydroOJAuth 认证对象
            tags: 题目标签列表（可选），用于更精确的匹配
            
        Returns:
            题目ID（如果找到精确匹配），否则返回 None
        """
        if not title:
            return None
        
        try:
            from urllib.parse import quote
            search_url = f"{self.base_url}/d/{self.domain}/p?q={quote(title)}"
            logger.debug(f"[HydroOJ Upload] 搜索题目: {search_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Referer': f"{self.base_url}/d/{self.domain}/p",
            }
            
            r = auth.session.get(search_url, headers=headers, timeout=30)
            r.raise_for_status()
            
            # 解析搜索结果，找到所有题目行
            target_title = title.strip()
            problem_rows = re.finditer(
                r'<tr[^>]*data-pid="([^"]+)"[^>]*>(.*?)</tr>',
                r.text,
                re.DOTALL
            )
            
            for row_match in problem_rows:
                pid = row_match.group(1)
                row_html = row_match.group(2)
                
                # 提取题目标题
                title_match = re.search(r'<a[^>]*>([^<]+)</a>', row_html)
                if not title_match:
                    continue
                
                found_title = title_match.group(1).strip()
                
                # 精确标题匹配
                if found_title != target_title:
                    continue
                
                # 如果有 tags，进一步验证标签
                if tags:
                    found_tags = []
                    tag_matches = re.finditer(r'<[^>]*class="[^"]*badge[^"]*"[^>]*>([^<]+)</', row_html)
                    for tag_match in tag_matches:
                        tag_text = tag_match.group(1).strip()
                        if tag_text:
                            found_tags.append(tag_text)
                    
                    # 检查标签匹配
                    tag_matched = any(
                        tag in found_tags or any(ftag in tag for ftag in found_tags) 
                        for tag in tags
                    )
                    if tag_matched:
                        logger.info(f"[HydroOJ Upload] 精确匹配找到题目: {pid} (标题: {found_title}, 标签: {found_tags})")
                        return pid
                    # 标签不匹配，但标题精确匹配，仍然返回
                    logger.debug(f"[HydroOJ Upload] 标题精确匹配但标签不匹配: {pid} (期望标签: {tags}, 实际: {found_tags})")
                
                # 标题精确匹配，返回
                logger.info(f"[HydroOJ Upload] 精确匹配找到题目: {pid} (标题: {found_title})")
                return pid
            
            logger.debug(f"[HydroOJ Upload] 未找到精确匹配 '{target_title}' 的题目")
            return None
        except Exception as e:
            logger.debug(f"[HydroOJ Upload] 搜索题目失败: {e}")
            return None
    
    def _get_latest_problem_id(self, auth: Any) -> Optional[str]:
        """通过题目标题搜索获取题目ID（精确匹配）
        
        复用 _search_exact_title 方法，避免代码重复。
        
        Args:
            auth: HydroOJAuth 认证对象
            
        Returns:
            题目ID，如果获取失败返回 None
        """
        title = getattr(self, '_last_upload_title', '')
        if not title:
            logger.warning(f"[HydroOJ Upload] 题目标题为空，无法搜索")
            return None
        
        result = self._search_exact_title(title, auth)
        if result:
            logger.info(f"[HydroOJ Upload] 通过标题搜索找到题目ID: {result}")
        else:
            logger.warning(f"[HydroOJ Upload] 未找到精确匹配 '{title}' 的题目")
        return result
    
    def _create_problem_md(self, problem_data: Dict) -> str:
        """生成 Markdown 题面（Hydro格式）"""
        md_lines = []
        
        # 标题
        title = problem_data.get('title', '未命名题目')
        md_lines.append(f"## {title}\n")
        
        # 描述
        if problem_data.get('description'):
            md_lines.append(f"{problem_data['description']}\n")
        
        # 输入格式
        if problem_data.get('input_format'):
            md_lines.append("## 输入格式\n")
            md_lines.append(f"{problem_data['input_format']}\n")
        
        # 输出格式
        if problem_data.get('output_format'):
            md_lines.append("## 输出格式\n")
            md_lines.append(f"{problem_data['output_format']}\n")
        
        # 样例（Hydro 顶格代码块格式）
        samples = problem_data.get('samples', [])
        if samples:
            for i, sample in enumerate(samples, 1):
                md_lines.append(f"```input{i}\n")
                md_lines.append(f"{sample.get('input', '').strip()}\n")
                md_lines.append("```\n")
                md_lines.append(f"```output{i}\n")
                md_lines.append(f"{sample.get('output', '').strip()}\n")
                md_lines.append("```\n")
        
        # 提示/说明
        if problem_data.get('hints'):
            md_lines.append("## 提示\n")
            md_lines.append(f"{problem_data['hints']}\n")
        
        # 数据范围（如果hints中没有，尝试从其他字段提取）
        if problem_data.get('time_limit') or problem_data.get('memory_limit'):
            if '## 提示' not in "\n".join(md_lines):
                md_lines.append("## 数据范围\n")
            if problem_data.get('time_limit'):
                md_lines.append(f"时间限制: {problem_data['time_limit']}ms\n")
            if problem_data.get('memory_limit'):
                md_lines.append(f"内存限制: {problem_data['memory_limit']}MB\n")
        
        return "\n".join(md_lines)
    
    def _create_problem_yaml(self, problem_data: Dict, pid: str) -> str:
        """生成 problem.yaml 配置"""
        # 提取时间和内存限制
        time_limit = problem_data.get('time_limit')
        if time_limit and time_limit > 1000:
            # 如果是毫秒，保持原值
            time_limit_val = int(time_limit)
        elif time_limit:
            # 如果是秒，转为毫秒
            time_limit_val = int(time_limit * 1000)
        else:
            time_limit_val = 1000
        
        memory_limit = problem_data.get('memory_limit') or 256
        
        tags = problem_data.get('tags', []) if problem_data.get('tags') else []
        logger.debug(f"[HydroOJ] 题目 {pid} 标签: {tags}")
        
        config = {
            'title': problem_data.get('title', '未命名题目'),
            'pid': pid,
            'tag': tags,
            'difficulty': str(problem_data.get('difficulty', '未知')),
            'time_limit': time_limit_val,
            'memory_limit': int(memory_limit)
        }
        return yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    
    def _pack_hydro_zip(self, problem_data: Dict, testdata_dir: Path, 
                         output_zip: Path, pid: str) -> Path:
        """打包为 Hydro 格式 ZIP"""
        # 使用题目标题作为目录名（添加 -std 后缀）
        title = problem_data.get('title', 'problem')
        # 移除文件名中的非法字符
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        
        with tempfile.TemporaryDirectory() as td:
            tmp_root = Path(td)
            prob_dir = tmp_root / f"{safe_title}-std"
            prob_dir.mkdir(parents=True)
            
            # 写入 problem_zh.md
            md_content = self._create_problem_md(problem_data)
            (prob_dir / "problem_zh.md").write_text(md_content, encoding='utf-8')
            logger.debug(f"生成 problem_zh.md，长度: {len(md_content)}")
            
            # 写入 problem.yaml
            yaml_content = self._create_problem_yaml(problem_data, pid)
            (prob_dir / "problem.yaml").write_text(yaml_content, encoding='utf-8')
            logger.debug(f"生成 problem.yaml")
            
            # 复制并重命名测试数据（0-based → 1-based）
            td_dest = prob_dir / "testdata"
            td_dest.mkdir()
            
            test_files = sorted(testdata_dir.glob('*.in'))
            test_files.extend(sorted(testdata_dir.glob('*.out')))
            test_files.extend(sorted(testdata_dir.glob('*.ans')))
            
            for test_file in test_files:
                stem = test_file.stem
                suffix = test_file.suffix
                
                # 如果是数字文件名，重命名为1-based
                if stem.isdigit():
                    new_num = int(stem) + 1
                    new_name = f"{new_num}{suffix}"
                    shutil.copy2(test_file, td_dest / new_name)
                    logger.debug(f"复制测试文件: {test_file.name} → {new_name}")
                else:
                    shutil.copy2(test_file, td_dest / test_file.name)
            
            # 打包为ZIP
            # shutil.make_archive 会自动添加.zip后缀
            archive_base = str(output_zip.with_suffix(''))
            shutil.make_archive(archive_base, 'zip', tmp_root, prob_dir.name)
            logger.info(f"打包完成: {output_zip}")
        
        return output_zip
    
    def _upload_to_hydro(self, zip_path: Path, auth: Any) -> Dict[str, Any]:
        """上传到 HydroOJ
        
        Args:
            zip_path: Hydro格式的ZIP文件路径
            auth: HydroOJAuth 认证对象
            
        Returns:
            上传结果
        """
        url = f"{self.base_url}/d/{self.domain}/problem/import/hydro"
        
        logger.info(f"上传到 HydroOJ: {url}")
        logger.info(f"ZIP文件: {zip_path.name}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': url,
            'Origin': self.base_url,
            'Accept': '*/*'
        }
        
        data = {'preferredPrefix': self.preferred_prefix or ''}
        
        logger.debug(f"[HydroOJ Upload] 准备上传请求")
        logger.debug(f"[HydroOJ Upload] URL: {url}")
        logger.debug(f"[HydroOJ Upload] Session Cookies: {len(auth.session.cookies)} 个")
        for cookie in auth.session.cookies:
            logger.debug(f"[HydroOJ Upload]   Cookie: {cookie.name} (domain={cookie.domain})")
        
        with open(zip_path, 'rb') as f:
            files = {'file': (zip_path.name, f, 'application/zip')}
            r = auth.session.post(
                url, 
                data=data, 
                files=files, 
                headers=headers, 
                allow_redirects=False,
                timeout=60
            )
        
        logger.debug(f"[HydroOJ Upload] 响应 headers: {dict(r.headers)}")
        logger.info(f"上传响应: HTTP {r.status_code}")
        logger.debug(f"[HydroOJ Upload] 响应体长度: {len(r.text)} 字符")
        logger.debug(f"[HydroOJ Upload] 响应体内容 (前1000字符): {r.text[:1000]}")
        
        # 检查是否成功
        if r.status_code == 200:
            # 直接成功，尝试从响应体提取题目ID
            real_id = None
            try:
                # 尝试解析 JSON 响应
                if r.text.strip():
                    import json
                    response_data = json.loads(r.text)
                    logger.debug(f"[HydroOJ Upload] JSON 响应: {response_data}")
                    
                    # 尝试多种可能的字段名
                    real_id = (response_data.get('pid') or 
                              response_data.get('problemId') or 
                              response_data.get('id') or
                              response_data.get('data', {}).get('pid') or
                              response_data.get('data', {}).get('problemId') or
                              response_data.get('data', {}).get('id'))
                    
                    if real_id:
                        logger.info(f"[HydroOJ Upload] 从 JSON 响应提取到题目ID: {real_id}")
            except (json.JSONDecodeError, Exception) as e:
                logger.debug(f"[HydroOJ Upload] 无法解析 JSON 响应: {e}")
            
            # 回退：如果从响应中无法获取 real_id，通过标题搜索获取（带重试机制解决索引延迟）
            if not real_id:
                logger.debug(f"[HydroOJ Upload] 响应中无 real_id，尝试通过标题搜索获取...")
                
                # 等待搜索索引更新（最多重试 3 次，每次等待时间递增）
                for retry in range(3):
                    if retry > 0:
                        wait_time = retry * 1.5  # 1.5s, 3s
                        logger.debug(f"[HydroOJ Upload] 等待 {wait_time}s 后重试搜索 (第 {retry + 1} 次)...")
                        time.sleep(wait_time)
                    
                    real_id = self._get_latest_problem_id(auth)
                    if real_id:
                        logger.info(f"[HydroOJ Upload] 通过标题搜索获取到题目ID: {real_id}")
                        break
                else:
                    logger.warning(f"[HydroOJ Upload] 搜索索引延迟，3 次重试后仍未找到题目ID")
            
            logger.info(f"✓ 上传成功: {zip_path.name}")
            result = {
                "status": "success", 
                "code": 200, 
                "file": zip_path.name,
                "http_status": r.status_code
            }
            if real_id:
                result["real_id"] = str(real_id)
                logger.info(f"[HydroOJ Upload] 题目真实ID: {real_id}")
            else:
                logger.warning(f"[HydroOJ Upload] ⚠ 未能获取题目ID，上传链接将不可用")
            return result
        elif r.status_code == 302:
            # 重定向需要检查目标
            redirect_location = r.headers.get('Location', '')
            logger.info(f"上传响应: HTTP {r.status_code}，重定向到: {redirect_location}")
            logger.debug(f"[HydroOJ Upload] 完整 Location header: {redirect_location}")
            
            # 检查是否重定向到错误页面（更严格的检测）
            redirect_lower = redirect_location.lower()
            error_patterns = ['/login', '/error', 'auth', 'permission', 'signin']
            
            # 检查是否是相对路径的登录页面
            is_error = False
            if '/login' in redirect_lower or '/signin' in redirect_lower:
                is_error = True
            elif '/error' in redirect_lower:
                is_error = True
            elif 'auth' in redirect_lower and ('fail' in redirect_lower or 'denied' in redirect_lower):
                is_error = True
            
            if is_error:
                # 重定向到错误页面（如登录页），视为失败
                logger.error(f"✗ 上传失败: 被重定向到登录页面，说明 Cookie 已失效")
                logger.error(f"重定向地址: {redirect_location}")
                raise RuntimeError(f"上传失败: Cookie 已失效或权限不足（重定向到登录页面）。请检查 HydroOJ 配置中的 sid 和 sid.sig 是否正确，或使用'自动获取 Cookie'功能重新获取。")
            else:
                # 重定向到正常页面，尝试从 URL 中提取题目ID
                real_id = None
                try:
                    # 尝试从重定向 URL 中提取题目ID
                    # 格式可能是: /d/{domain}/problem/{pid} 或 /d/{domain}/p/{pid}
                    # 匹配 /problem/{pid} 或 /p/{pid}
                    match = re.search(r'/problem/([^/?]+)', redirect_location)
                    if not match:
                        match = re.search(r'/p/([^/?]+)', redirect_location)
                    if match:
                        real_id = match.group(1)
                        logger.info(f"[HydroOJ Upload] 从重定向 URL 提取到题目ID: {real_id}")
                    else:
                        # 如果重定向到题目列表页（/d/{domain}/p），尝试获取最新题目
                        if '/p' in redirect_location and redirect_location.endswith('/p'):
                            logger.debug(f"[HydroOJ Upload] 重定向到题目列表，尝试获取最新题目ID")
                            real_id = self._get_latest_problem_id(auth)
                            if real_id:
                                logger.info(f"[HydroOJ Upload] 从题目列表获取到最新题目ID: {real_id}")
                except Exception as e:
                    logger.debug(f"[HydroOJ Upload] 提取题目ID失败: {e}")
                
                # 重定向到正常页面（如题目列表），视为成功（PRG模式）
                logger.info(f"✓ 上传成功 (HTTP 302 重定向到: {redirect_location})")
                result = {
                    "status": "success", 
                    "code": 200, 
                    "file": zip_path.name,
                    "http_status": r.status_code,
                    "redirect_to": redirect_location
                }
                if real_id:
                    result["real_id"] = real_id
                    logger.info(f"[HydroOJ Upload] 题目真实ID: {real_id}")
                else:
                    logger.warning(f"[HydroOJ Upload] 未能提取题目ID，求解功能将不可用")
                return result
        else:
            logger.error(f"上传失败: HTTP {r.status_code}")
            logger.debug(f"响应内容: {r.text[:500]}")
            # 针对不同错误码给出更具体的提示
            if r.status_code == 404:
                raise RuntimeError(
                    f"上传失败: HTTP 404\n"
                    f"可能原因:\n"
                    f"  1. 域名 (domain) '{self.domain}' 在 HydroOJ 上不存在\n"
                    f"  2. 您没有该域的创建题目权限\n"
                    f"  3. base_url 配置错误: {self.base_url}\n"
                    f"请检查 HydroOJ 配置中的 base_url 和 domain 是否正确。"
                )
            elif r.status_code == 403:
                raise RuntimeError(
                    f"上传失败: HTTP 403 权限不足\n"
                    f"您可能没有在域 '{self.domain}' 创建题目的权限。\n"
                    f"请联系管理员授权，或检查 Cookie 是否已失效。"
                )
            else:
                raise RuntimeError(f"上传失败: HTTP {r.status_code}")
    
    # ========== 增量更新方法 ==========
    
    def _collect_test_files(self, testdata_dir: Path) -> List[Path]:
        """收集本地测试文件（成对的 .in/.out）
        
        Args:
            testdata_dir: 测试数据目录
            
        Returns:
            文件路径列表（按数值序，成对）
        """
        ins = {}
        outs = {}
        
        for file in testdata_dir.glob("*"):
            if file.is_file():
                match_in = re.match(r'^(\d+)\.in$', file.name)
                match_out = re.match(r'^(\d+)\.out$', file.name)
                if match_in:
                    ins[match_in.group(1)] = file
                if match_out:
                    outs[match_out.group(1)] = file
        
        # 只返回成对的文件
        indices = sorted(set(ins.keys()) & set(outs.keys()), key=lambda x: int(x))
        files = []
        for idx in indices:
            files.extend([ins[idx], outs[idx]])
        
        # 警告：不成对的文件
        all_indices = set(ins.keys()) | set(outs.keys())
        for idx in all_indices:
            if idx not in ins:
                logger.warning(f"缺少 {idx}.in，跳过该编号")
            elif idx not in outs:
                logger.warning(f"缺少 {idx}.out，跳过该编号")
        
        return files
    
    def _list_remote_testdata(self, problem_id: str, auth: Any) -> List[str]:
        """列出远端 testdata 目录的文件
        
        Args:
            problem_id: HydroOJ 题目 ID
            auth: HydroOJAuth 认证对象
            
        Returns:
            远端文件名列表
        """
        url = f"{self.base_url}/d/{self.domain}/p/{problem_id}/files"
        params = {"d": "testdata", "sidebar": "true", "pjax": "1"}
        
        try:
            r = auth.session.get(url, params=params, timeout=30)
            r.raise_for_status()
            
            # 从响应中提取文件名（使用正则）
            html = r.text
            names = re.findall(r'>([^<]+\.(?:in|out))<', html)
            unique_names = sorted(set(names))
            
            logger.debug(f"[HydroOJ Upload] 远端文件列表: {unique_names}")
            return unique_names
        except Exception as e:
            logger.warning(f"[HydroOJ Upload] 列出远端文件失败: {e}")
            return []
    
    def _delete_testdata_files(self, problem_id: str, files: List[str], auth: Any):
        """删除远端测试数据文件
        
        Args:
            problem_id: HydroOJ 题目 ID
            files: 要删除的文件名列表
            auth: HydroOJAuth 认证对象
        """
        if not files:
            return
        
        url = f"{self.base_url}/d/{self.domain}/p/{problem_id}/files"
        
        # 分批删除（每批20个）
        batch_size = 20
        for i in range(0, len(files), batch_size):
            batch = files[i:i+batch_size]
            payload = {
                "operation": "delete_files",
                "files": batch,
                "type": "testdata"
            }
            
            logger.debug(f"[HydroOJ Upload] 删除文件批次: {batch}")
            r = auth.session.post(url, json=payload, timeout=60)
            
            if r.status_code >= 400:
                logger.error(f"[HydroOJ Upload] 删除文件失败: HTTP {r.status_code}")
                raise RuntimeError(f"删除文件失败（HTTP {r.status_code}）: {r.text[:300]}")
            
            time.sleep(0.2)  # 轻量限速
    
    def _upload_single_file(self, problem_id: str, file_path: Path, auth: Any):
        """上传单个测试数据文件
        
        Args:
            problem_id: HydroOJ 题目 ID
            file_path: 文件路径
            auth: HydroOJAuth 认证对象
        """
        url = f"{self.base_url}/d/{self.domain}/p/{problem_id}/files"
        
        with open(file_path, 'rb') as f:
            files = {
                "file": (file_path.name, f, "application/octet-stream")
            }
            data = {
                "filename": file_path.name,
                "type": "testdata",
                "operation": "upload_file"
            }
            
            r = auth.session.post(url, files=files, data=data, timeout=120)
            
            if r.status_code >= 400:
                logger.error(f"[HydroOJ Upload] 上传 {file_path.name} 失败: HTTP {r.status_code}")
                raise RuntimeError(f"上传 {file_path.name} 失败（HTTP {r.status_code}）: {r.text[:300]}")
            
            logger.debug(f"[HydroOJ Upload] 已上传: {file_path.name}")
    
    def _update_testdata(self, problem_id: str, testdata_dir: Path, auth: Any) -> Dict[str, Any]:
        """更新已存在题目的测试数据
        
        流程：
        1. 收集本地文件
        2. 列出远端文件
        3. 删除所有远端文件
        4. 逐个上传本地文件
        
        Args:
            problem_id: HydroOJ 题目 ID（real_id）
            testdata_dir: 本地测试数据目录
            auth: HydroOJAuth 认证对象
            
        Returns:
            更新结果
        """
        logger.info(f"[HydroOJ Upload] ========== 开始更新题目 {problem_id} 的测试数据 ==========")
        
        # 收集本地文件
        logger.info(f"[HydroOJ Upload] 步骤 1/4: 收集本地文件")
        local_files = self._collect_test_files(testdata_dir)
        if not local_files:
            raise RuntimeError("本地测试数据为空")
        
        logger.info(f"[HydroOJ Upload] 本地文件: {len(local_files)} 个 - {[f.name for f in local_files[:10]]}")
        
        # 列出远端文件
        logger.info(f"[HydroOJ Upload] 步骤 2/4: 列出远端文件")
        remote_files = self._list_remote_testdata(problem_id, auth)
        logger.info(f"[HydroOJ Upload] 远端文件: {len(remote_files)} 个 - {remote_files[:10] if remote_files else '无'}")
        
        # 删除所有远端文件（清空后重新上传）
        logger.info(f"[HydroOJ Upload] 步骤 3/4: 删除远端文件")
        to_delete = [name for name in remote_files]
        
        if to_delete:
            logger.info(f"[HydroOJ Upload] 将删除 {len(to_delete)} 个远端文件")
            self._delete_testdata_files(problem_id, to_delete, auth)
            logger.info(f"[HydroOJ Upload] ✓ 删除完成")
        else:
            logger.info(f"[HydroOJ Upload] 远端无文件，跳过删除")
        
        # 逐个上传文件
        logger.info(f"[HydroOJ Upload] 步骤 4/4: 上传本地文件")
        logger.info(f"[HydroOJ Upload] 开始上传 {len(local_files)} 个文件")
        
        upload_count = 0
        for file_path in local_files:
            self._upload_single_file(problem_id, file_path, auth)
            upload_count += 1
            if upload_count % 5 == 0:
                logger.info(f"[HydroOJ Upload] 进度: {upload_count}/{len(local_files)}")
            time.sleep(0.1)  # 轻量限速
        
        logger.info(f"[HydroOJ Upload] ✓ 全部上传完成 ({upload_count} 个文件)")
        logger.info(f"[HydroOJ Upload] ========== 测试数据更新完成 ==========")
        
        return {
            "status": "success",
            "code": 200,
            "file": f"updated_{len(local_files)}_files",  # 修复 unknown 的问题
            "message": f"已更新 {len(local_files)} 个文件",
            "real_id": problem_id,
            "updated": True
        }
