# -*- coding: utf-8 -*-
"""SHSOJ数据上传实现（适配新接口）"""

from typing import Dict, Any
from pathlib import Path
import json, time, os
from loguru import logger

from ...base.data_uploader import DataUploader
from .url_utils import derive_api_url, derive_frontend_url


class SHSOJDataUploader(DataUploader):
    """SHSOJ数据上传器（实现新接口）"""
    
    def __init__(self, base_url: str, timeout: int, proxies: dict = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.proxies = proxies
        self.verify_ssl = verify_ssl
        # 推导API URL（确保使用正确的API端点）
        self.api_base_url = derive_api_url(self.base_url)
    
    def _clean_payload_for_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """清理payload中可能导致SHSOJ API解析错误的字段
        
        常见问题:
        1. None值应该被移除或替换为空字符串/默认值
        2. 数值字段必须是正确的类型（int/float）
        3. 某些字段不能是空对象或空数组
        """
        import copy
        cleaned = copy.deepcopy(payload)
        
        # 清理problem对象中的字段
        prob = cleaned.get("problem", {})
        
        # 注意：SHSOJ API 需要这些字段存在（即使是 null），不要删除它们
        # 参考 wash.py 的 prepare_update_payload 函数，它不删除任何字段
        # 以下字段如果不存在，需要添加为 null（与抓包数据一致）
        nullable_fields_to_ensure = [
            "spjLanguage", "spjCode", "userExtraFile", "judgeExtraFile",
            "ioReadFileName", "ioWriteFileName", "gid", "questionBankId", "questionChapterId"
        ]
        for field in nullable_fields_to_ensure:
            if field not in prob:
                prob[field] = None
        
        # 确保 contestProblem 存在（空对象）
        if "contestProblem" not in prob:
            prob["contestProblem"] = {}
        
        # 需要转为空字符串的字段（如果是None）
        string_fields = [
            "problemId", "title", "description", "input", "output", "examples", 
            "hint", "source", "author"
        ]
        for field in string_fields:
            if field in prob and prob[field] is None:
                prob[field] = ""
        
        # 确保数值字段是正确类型
        int_fields = ["id", "timeLimit", "memoryLimit", "stackLimit", "difficulty", "type", "auth"]
        for field in int_fields:
            if field in prob and prob[field] is not None:
                try:
                    prob[field] = int(prob[field])
                except (ValueError, TypeError):
                    pass
        
        # 确保布尔字段是正确类型
        # 注意：isDeleted 应保持为整数（0/1），不转为 bool
        bool_fields = ["codeShare", "spjCompileOk", "isUploadCase", "isRemoveEndBlank", 
                       "openCaseResult", "isFileIO", "isGroup", "isRemote"]
        for field in bool_fields:
            if field in prob:
                if prob[field] is None:
                    prob[field] = False
                elif not isinstance(prob[field], bool):
                    prob[field] = bool(prob[field])
        
        # isDeleted 保持为整数类型（0 或 1）
        if "isDeleted" in prob:
            if prob["isDeleted"] is None:
                prob["isDeleted"] = 0
            elif isinstance(prob["isDeleted"], bool):
                prob["isDeleted"] = 1 if prob["isDeleted"] else 0
        
        # 确保contestProblem是对象（不是None）- 如果存在但是None，转为空对象
        if prob.get("contestProblem") is None:
            prob["contestProblem"] = {}
        
        # 清理testCaseScore - 确保每个元素都有正确的字段
        if "testCaseScore" in prob and isinstance(prob["testCaseScore"], list):
            cleaned_scores = []
            for i, item in enumerate(prob["testCaseScore"]):
                if isinstance(item, dict):
                    cleaned_item = {
                        "input": item.get("input", f"{i}.in"),
                        "output": item.get("output", f"{i}.out"),
                        "score": int(item.get("score", 10)),
                        "pid": item.get("pid"),
                        "index": int(item.get("index", i + 1)),
                        "_XID": item.get("_XID", f"row_{i + 6}")
                    }
                    # 移除pid如果是None
                    if cleaned_item["pid"] is None:
                        del cleaned_item["pid"]
                    cleaned_scores.append(cleaned_item)
            prob["testCaseScore"] = cleaned_scores
        
        cleaned["problem"] = prob
        
        # 清理顶层samples字段 - 与 testCaseScore 保持完全一致的字段顺序和处理逻辑
        if "samples" in cleaned and isinstance(cleaned["samples"], list):
            cleaned_samples = []
            for i, item in enumerate(cleaned["samples"]):
                if isinstance(item, dict):
                    # 字段顺序必须与 testCaseScore 完全一致：input, output, score, pid, index, _XID
                    cleaned_item = {
                        "input": item.get("input", f"{i}.in"),
                        "output": item.get("output", f"{i}.out"),
                        "score": int(item.get("score", 10)),
                        "pid": item.get("pid"),
                        "index": int(item.get("index", i + 1)),
                        "_XID": item.get("_XID", f"row_{i + 6}")
                    }
                    # 移除pid如果是None - 与 testCaseScore 一致
                    if cleaned_item["pid"] is None:
                        del cleaned_item["pid"]
                    cleaned_samples.append(cleaned_item)
            cleaned["samples"] = cleaned_samples
        
        # 确保必需的顶层字段存在
        if "tags" not in cleaned:
            cleaned["tags"] = []
        if "codeTemplates" not in cleaned:
            cleaned["codeTemplates"] = []
        
        # 移除顶层None值
        keys_to_remove = [k for k, v in cleaned.items() if v is None]
        for k in keys_to_remove:
            del cleaned[k]
        
        return cleaned
    
    def upload_testcase(self, problem_id: str, data_path: Path, auth: Any) -> Dict[str, Any]:
        """上传测试数据
        
        Args:
            problem_id: 题目ID
            data_path: 数据路径（zip文件）
            auth: SHSOJ认证对象
            
        Returns:
            上传结果
        """
        if not data_path.exists():
            raise FileNotFoundError(f"数据文件不存在: {data_path}")
        
        # SHSOJ只支持zip格式
        if data_path.suffix != '.zip':
            raise ValueError(f"SHSOJ仅支持zip格式，当前: {data_path.suffix}")
        
        return self.upload_testcase_zip(auth, str(data_path))
    
    def supports_format(self, format_type: str) -> bool:
        """SHSOJ只支持zip格式"""
        return format_type.lower() == 'zip'
    
    def upload_testcase_zip(self, auth, zip_path: str, mode: str = "default") -> Dict[str, Any]:
        """上传测试数据ZIP包（SHSOJ原生API）"""
        if auth is None:
            raise RuntimeError("认证对象为 None，无法上传。请先登录。")
        
        url = f"{self.api_base_url}/api/file/upload-testcase-zip?mode={mode}"
        
        # 读取文件
        with open(zip_path, "rb") as f:
            file_data = f.read()
        
        filename = os.path.basename(zip_path)
        
        # 构建multipart/form-data
        boundary = "----WebKitFormBoundary%08x%08x" % (int(time.time()) & 0xFFFFFFFF, os.getpid() & 0xFFFFFFFF)
        file_ct = "application/x-zip-compressed"
        crlf = "\r\n"
        
        lines = []
        lines.append(f"--{boundary}")
        lines.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"')
        lines.append(f"Content-Type: {file_ct}")
        lines.append("")
        
        body_head = crlf.join(lines).encode("utf-8") + crlf.encode("utf-8")
        body_tail = (crlf + f"--{boundary}--" + crlf).encode("utf-8")
        body = body_head + file_data + body_tail
        
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "Accept": "*/*",
            "Origin": self.api_base_url.replace("-api", "").replace("api-tcoj", "oj"),
            "Referer": self.api_base_url.replace("-api", "").replace("api-tcoj", "oj") + "/",
            "User-Agent": "Mozilla/5.0",
            "authorization": auth.token,
            "url-type": "general",
        }
        
        r = auth.session.post(url, data=body, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        
        if r.status_code != 200:
            raise RuntimeError(f"上传失败: HTTP {r.status_code} {r.reason}")
        
        json_resp = r.json()
        if json_resp.get("code") not in (0, 200):
            raise RuntimeError(f"上传返回错误: {json_resp}")
        
        return json_resp.get("data", {})
    
    def fetch_problem_cases(self, auth, pid: int):
        """触发服务器解析测试用例"""
        url = f"{self.api_base_url}/api/admin/problem/get-problem-cases?pid={pid}&isUpload=true"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
            "User-Agent": "Mozilla/5.0",
        }
        
        r = auth.session.get(url, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        if r.status_code != 200:
            return []
        
        obj = r.json()
        if obj.get("code") in (0, 200):
            return obj.get("data", []) or []
        return []
    
    def put_admin_problem(self, auth, pid: int, payload: Dict[str, Any]):
        """更新题目配置"""
        url = f"{self.api_base_url}/api/admin/problem"
        
        # 注意：旧代码没有 _clean_payload_for_update 步骤，直接发送原始 payload
        # 经对比验证，清理步骤可能导致 "Failed to parse parameter format!" 错误
        # 只做最小限度的类型修正，不重新构建数组
        final_payload = payload
        
        # 仅确保 isDeleted 是整数（0/1），不是 bool - 这是唯一已确认的类型问题
        prob = final_payload.get("problem", {})
        if "isDeleted" in prob and isinstance(prob["isDeleted"], bool):
            prob["isDeleted"] = 1 if prob["isDeleted"] else 0
        
        data_bytes = json.dumps(final_payload, ensure_ascii=False).encode("utf-8")
        frontend_url = derive_frontend_url(self.api_base_url)
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
            "Origin": frontend_url,
            "Referer": f"{frontend_url}/",
            "User-Agent": "Mozilla/5.0",
        }
        
        # 调试：记录发送的payload关键信息
        logger.debug(f"[put_admin_problem] 发送更新请求: pid={pid}, title={prob.get('title')}, type={prob.get('type')}")
        logger.debug(f"[put_admin_problem] testCaseScore数量: {len(prob.get('testCaseScore', []))}")
        logger.debug(f"[put_admin_problem] languages数量: {len(final_payload.get('languages', []))}")
        
        attempt_payload = final_payload
        r = auth.session.put(url, data=data_bytes, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)

        if r.status_code != 200:
            # If the server cannot parse a non-numeric problemId, retry once with numeric pid.
            retry_needed = False
            try:
                if r.status_code == 400:
                    try:
                        err_obj = r.json()
                        err_msg = err_obj.get("msg") or err_obj.get("message") or ""
                    except Exception:
                        err_msg = r.text or ""
                    if "Failed to parse parameter format" in err_msg:
                        current_pid = str(final_payload.get("problem", {}).get("problemId") or "").strip()
                        if current_pid and not current_pid.isdigit():
                            retry_needed = True
            except Exception:
                retry_needed = False

            if retry_needed:
                try:
                    import copy
                    retry_payload = copy.deepcopy(final_payload)
                    retry_prob = retry_payload.get("problem", {})
                    retry_prob["problemId"] = str(pid)
                    retry_payload["problem"] = retry_prob
                    data_bytes = json.dumps(retry_payload, ensure_ascii=False).encode("utf-8")
                    logger.warning(
                        "[put_admin_problem] retry with numeric problemId after parse error: %s -> %s",
                        final_payload.get("problem", {}).get("problemId"),
                        retry_prob.get("problemId"),
                    )
                    attempt_payload = retry_payload
                    r = auth.session.put(url, data=data_bytes, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
                except Exception as retry_exc:
                    logger.warning(f"[put_admin_problem] retry failed to start: {retry_exc}")

        if r.status_code != 200:
            # 记录详细的错误信息以便调试
            error_detail = ""
            try:
                error_detail = f", 响应: {r.text[:1000]}"
            except Exception:
                try:
                    error_detail = f", 响应内容长度: {len(r.content)} 字节"
                except Exception:
                    pass
            logger.error(f"更新题目配置失败: HTTP {r.status_code}{error_detail}, URL: {url}, PID: {pid}")
            
            # 在日志中直接输出 payload 关键信息用于调试
            try:
                prob = attempt_payload.get("problem", {})
                test_case_score = prob.get("testCaseScore", [])
                samples = attempt_payload.get("samples", [])
                
                # 输出 testCaseScore 的第一个元素结构（检查字段）
                if test_case_score and len(test_case_score) > 0:
                    first_case = test_case_score[0]
                    logger.error(f"[DEBUG] testCaseScore[0] 字段: {list(first_case.keys())}")
                    logger.error(f"[DEBUG] testCaseScore[0] 内容: {json.dumps(first_case, ensure_ascii=False, indent=2)}")
                else:
                    logger.error(f"[DEBUG] testCaseScore 为空或不存在")
                
                # 输出 samples 的第一个元素结构
                if samples and len(samples) > 0:
                    first_sample = samples[0]
                    logger.error(f"[DEBUG] samples[0] 字段: {list(first_sample.keys())}")
                    logger.error(f"[DEBUG] samples[0] 内容: {json.dumps(first_sample, ensure_ascii=False, indent=2)}")
                else:
                    logger.error(f"[DEBUG] samples 为空或不存在")
                
                # 输出顶层字段
                logger.error(f"[DEBUG] payload 顶层字段: {list(attempt_payload.keys())}")
                logger.error(f"[DEBUG] problem 字段数: {len(prob)}, testCaseScore数量: {len(test_case_score)}, samples数量: {len(samples)}")
                
                # 输出 problem 对象的所有字段名和值类型
                prob_fields_info = []
                for k, v in prob.items():
                    if k == "testCaseScore":
                        prob_fields_info.append(f"{k}=[{len(v)} items]")
                    elif isinstance(v, str) and len(v) > 50:
                        prob_fields_info.append(f"{k}=str({len(v)})")
                    elif v is None:
                        prob_fields_info.append(f"{k}=null")
                    else:
                        prob_fields_info.append(f"{k}={type(v).__name__}:{repr(v)[:30]}")
                logger.error(f"[DEBUG] problem 字段详情: {', '.join(prob_fields_info)}")
            except Exception as e:
                logger.error(f"[DEBUG] 输出payload调试信息失败: {e}")
            
            # 发生错误时，保存payload到文件用于调试
            try:
                import tempfile
                debug_file = Path(tempfile.gettempdir()) / f"shsoj_debug_payload_{pid}.json"
                debug_file.write_text(json.dumps(attempt_payload, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.error(f"已保存调试payload到: {debug_file}")
            except Exception as e:
                logger.debug(f"保存调试payload失败: {e}")
            raise RuntimeError(f"更新题目配置失败: HTTP {r.status_code}{error_detail}")
        
        obj = r.json()
        if obj.get("code") not in (0, 200):
            raise RuntimeError(f"更新题目配置返回错误: {obj}")
        
        return obj
    
    def check_problem_exists(self, auth, problem_id: str) -> tuple[bool, int | None]:
        """检查题目是否存在（通过problemId查找）
        
        Args:
            auth: SHSOJ认证对象
            problem_id: 题目ID（problemId字符串，如"1233"）
            
        Returns:
            (是否存在, 后端ID) 如果存在则返回后端ID，否则返回None
        """
        url = f"{self.api_base_url}/api/admin/problem/get-admin-problem-list"
        payload = {
            "problemId": str(problem_id),
            "tagIdList": [],
            "limit": 10,
            "currentPage": 1,
            "isGroup": False,
        }
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
        }
        
        try:
            r = auth.session.post(url, data=data_bytes, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
            if r.status_code == 200:
                obj = r.json()
                records = obj.get("data", {}).get("records", []) or []
                # 精确匹配problemId字段
                for rec in records:
                    if rec.get("problemId") == str(problem_id):
                        actual_id = rec.get("id")
                        return True, actual_id
        except Exception as e:
            logger.debug(f"检查题目是否存在失败: {e}")
        
        return False, None
    
    def create_problem(self, auth, problem_data: Dict[str, Any], upload_testcase_dir: str) -> Dict[str, Any]:
        """创建新题目
        
        Args:
            auth: SHSOJ认证对象
            problem_data: 题面数据（标准格式，来自problem_data.json）
            upload_testcase_dir: 已上传的测试数据目录（服务器路径，如"/opt/judge/file/zip/xxx"）
            
        Returns:
            创建结果，包含新题目的ID
        """
        url = f"{self.api_base_url}/api/admin/problem"
        
        # 从测试数据目录中提取文件列表
        # 先获取测试用例（需要先上传zip并解析）
        # 这里假设文件列表已经在problem_data中或需要从服务器获取
        
        # 字段验证和默认值设置
        if not problem_data.get("title"):
            problem_data["title"] = "未命名题目"
        if not problem_data.get("description"):
            problem_data["description"] = "题目描述"
        if not problem_data.get("input_format"):
            problem_data["input_format"] = "见题目描述"
        if not problem_data.get("output_format"):
            problem_data["output_format"] = "见题目描述"
        
        # 预先确定要使用的problemId（用于回填和查找）
        problem_id_guess = str(problem_data.get("id") or problem_data.get("problem_id") or "").strip()
        
        # 构建SHSOJ格式的payload
        # 将标准格式转换为SHSOJ格式
        samples = problem_data.get("samples", [])
        
        # 确保至少有一个样例
        if not samples:
            samples = [{"input": "1", "output": "1"}]
        
        examples_html = ""
        for sample in samples:
            inp = sample.get("input", "").strip()
            out = sample.get("output", "").strip()
            # 确保输入输出不为空
            if not inp:
                inp = "1"
            if not out:
                out = "1"
            examples_html += f"<input>{inp}</input><output>{out}</output>"
        
        # 构建testCaseScore和samples
        # 优先使用传入的_test_case_score和_samples_list（从上传结果中提取）
        test_case_score = problem_data.get("_test_case_score", [])
        samples_list = problem_data.get("_samples_list", [])
        
        # 如果没有提供，尝试从problem_data中推断（假设有samples信息）
        if not test_case_score:
            # 默认假设有0-9的测试用例，均分100分
            n = 10
            base = 100 // n
            extra = 100 - base * n
            for i in range(n):
                score = base + (1 if (i + 1) <= extra else 0)
                # 字段顺序与 wash.py normalize_test_cases 保持一致：input, output, score, pid, index, _XID
                test_case_score.append({
                    "input": f"{i}.in",
                    "output": f"{i}.out",
                    "score": score,
                    "pid": None,
                    "index": i + 1,
                    "_XID": f"row_{i + 6}"
                })
                samples_list.append({
                    "input": f"{i}.in",
                    "output": f"{i}.out",
                    "score": score,
                    "pid": None,
                    "index": i + 1,
                    "_XID": f"row_{i + 6}"
                })
        
        # 时间限制：安全处理，确保不为None
        time_limit = problem_data.get("time_limit")
        if time_limit is not None and time_limit > 1000:
            # 已经是毫秒
            time_limit_ms = int(time_limit)
        elif time_limit is not None:
            # 是秒，转换为毫秒
            time_limit_ms = int(time_limit * 1000)
        else:
            # 默认1秒 = 1000毫秒
            time_limit_ms = 1000
        
        # 内存限制：MB，确保是整数
        memory_limit_value = problem_data.get("memory_limit")
        if memory_limit_value is not None:
            memory_limit = int(memory_limit_value)
        else:
            memory_limit = 128
        
        # 获取languages配置（从problem_data中的_languages或使用默认配置）
        languages = problem_data.get("_languages", [])
        
        # 如果 languages 为空，使用默认的语言配置（SHSOJ 需要非空 languages）
        if not languages:
            logger.warning("languages 为空，使用默认的 C++/Python 配置")
            languages = [
                {
                    "id": 3, "contentType": "text/x-c++src", "description": "G++ 7.5.0",
                    "name": "C++", "compileCommand": "/usr/bin/g++ -DONLINE_JUDGE -w -fmax-errors=3 -std=c++14 {src_path} -lm -o {exe_path}",
                    "template": "#include<iostream>\nusing namespace std;\nint main() { int a,b; cin >> a >> b; cout << a + b; return 0; }",
                    "codeTemplate": "", "isSpj": True, "oj": "ME", "seq": 0
                },
                {
                    "id": 6, "contentType": "text/x-python", "description": "Python 3.7.5",
                    "name": "Python3", "compileCommand": "/usr/bin/python3 -m py_compile {src_path}",
                    "template": "a, b = map(int, input().split())\nprint(a + b)",
                    "codeTemplate": "", "isSpj": False, "oj": "ME", "seq": 0
                }
            ]
        
        payload = {
            "changeModeCode": True,
            "problem": {
                "id": None,
                # 若有原平台ID（如U232086），直接用作problemId，方便后续查找
                "problemId": problem_id_guess or "",
                "title": problem_data.get("title", "新题目"),
                "author": getattr(auth, "username", ""),
                "type": 1,  # OI模式
                "publishStatus": 1,  # 公开
                "judgeMode": "default",
                "judgeCaseMode": "default",
                "timeLimit": time_limit_ms,  # 已处理为毫秒
                "memoryLimit": memory_limit,
                "stackLimit": memory_limit,
                "description": problem_data.get("description", "题目描述"),
                "input": problem_data.get("input_format", "见题目描述"),
                "output": problem_data.get("output_format", "见题目描述"),
                "examples": examples_html,
                "isRemote": False,
                "source": problem_data.get("source", "").upper() if problem_data.get("source") else "",
                "difficulty": 0,
                "difficultyRadix": 0,
                "hint": problem_data.get("hints", ""),
                "auth": 1,
                "ioScore": 100,
                "codeShare": False,
                "spjCode": None,
                "spjLanguage": None,
                "userExtraFile": None,
                "judgeExtraFile": None,
                "isRemoveEndBlank": True,
                "openCaseResult": True,
                "isUploadCase": True,
                "uploadTestcaseDir": upload_testcase_dir,
                "testCaseScore": test_case_score,
                "isFileIO": False,
                "ioReadFileName": None,
                "ioWriteFileName": None,
                "isGroup": False,
                "gid": None,
                "questionBankId": None,
                "questionChapterId": None,
                "spjCompileOk": False,
                "contestProblem": {},
            },
            "codeTemplates": [],
            "tags": [],
            "languages": languages,  # 使用从template加载的languages
            "isUploadTestCase": True,
            "uploadTestcaseDir": upload_testcase_dir,
            "judgeMode": "default",
            "samples": samples_list,
            "changeJudgeCaseMode": True,
        }
        
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
        }
        
        # 记录请求详情（用于调试）
        logger.debug(f"创建题目payload标题: {payload['problem'].get('title')}")
        logger.debug(f"创建题目payload languages数: {len(payload.get('languages', []))}")
        logger.debug(f"创建题目payload samples数: {len(payload.get('samples', []))}")
        
        r = auth.session.post(url, data=data_bytes, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        
        if r.status_code != 200:
            # 尝试获取错误详情
            response_text = r.text[:1000] if r.text else "(empty)"
            logger.error(f"创建题目失败: HTTP {r.status_code}")
            logger.error(f"创建题目请求URL: {url}")
            logger.error(f"创建题目请求problemId: {payload['problem'].get('problemId')}")
            logger.error(f"创建题目请求title: {payload['problem'].get('title')}")
            logger.error(f"创建题目响应内容: {response_text}")
            
            try:
                error_detail = r.json()
                raise RuntimeError(f"创建题目失败: HTTP {r.status_code}, 详情: {error_detail.get('msg', 'unknown')}")
            except ValueError:
                # JSON 解析失败，返回原始响应
                raise RuntimeError(f"创建题目失败: HTTP {r.status_code}, 响应: {response_text[:200]}")
        
        try:
            obj = r.json()
        except Exception as json_err:
            logger.error(f"解析创建题目响应JSON失败: {json_err}, 响应内容: {r.text[:500]}")
            raise RuntimeError(f"解析响应JSON失败: {json_err}")
        
        if not obj:
            raise RuntimeError("创建题目失败：响应为空")
        
        if obj.get("code") not in (0, 200):
            logger.error(f"创建题目返回错误: {obj}")
            raise RuntimeError(f"创建题目返回错误: {obj.get('msg', 'unknown')}")
        
        # 某些情况下后端不返回data字段，此时尝试用problemId回填
        if not obj.get("data"):
            if problem_id_guess:
                try:
                    exists, existing_id = self.check_problem_exists(auth, problem_id_guess)
                    if exists and existing_id:
                        logger.warning(f"创建题目响应缺少data，已通过problemId={problem_id_guess} 回填ID={existing_id}")
                        obj["data"] = {"problem": {"id": existing_id, "problemId": problem_id_guess}}
                        return obj
                except Exception as e:
                    logger.warning(f"创建题目响应缺少data，且回填失败: {e}")
            raise RuntimeError(f"创建题目成功但响应缺少data字段: {obj}")
        
        logger.debug(f"创建题目成功响应: {obj}")
        return obj
