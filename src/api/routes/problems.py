# -*- coding: utf-8 -*-
"""
题目获取API
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from loguru import logger
import requests
from api.auth import get_current_user

router = APIRouter()

# AICoders API
AICODERS_API = "https://api-tcoj.aicoders.cn"


class ProblemInfo(BaseModel):
    """题目信息"""
    id: str
    title: Optional[str] = None
    url: str
    source: str  # 来源OJ


class ProblemListResponse(BaseModel):
    """题目列表响应"""
    total: int
    problems: List[ProblemInfo]


class TagInfo(BaseModel):
    """标签信息"""
    id: int
    name: str
    rank: int = 0
    classification: str = ""
    classification_id: Optional[int] = None


class TagClassification(BaseModel):
    """标签分类"""
    id: int
    name: str
    tags: List[TagInfo]


class TagGroup(BaseModel):
    """标签分组"""
    id: int
    name: str
    classifications: List[TagClassification]


class TagsResponse(BaseModel):
    """标签响应"""
    groups: List[TagGroup]
    total_tags: int


@router.get("/tags", response_model=TagsResponse)
async def get_all_tags():
    """
    从 AICoders 获取所有标签（分组和分类结构）
    
    Returns:
        标签分组列表
    """
    try:
        url = f"{AICODERS_API}/api/get-problem-tags-group"
        params = {"type": 0, "publishStatus": 1}
        
        logger.info(f"正在从 AICoders 获取标签: {url}")
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        
        if data.get("status") != 200:
            raise HTTPException(status_code=500, detail=f"获取标签失败: {data}")
        
        # 解析标签结构
        groups = []
        total_tags = 0
        raw_groups = data.get("data", [])
        
        for group in raw_groups:
            # 分组信息在 tagGroup 对象中
            tag_group = group.get("tagGroup", {})
            group_id = tag_group.get("id", 0)
            group_name = tag_group.get("name", "未分组")
            classifications = []
            
            for classification_item in group.get("classificationList", []):
                # 分类信息在 classification 对象中
                classification = classification_item.get("classification", {})
                class_id = classification.get("id", 0)
                class_name = classification.get("name", "")
                tags = []
                
                for tag in classification_item.get("tagList", []):
                    tags.append(TagInfo(
                        id=tag.get("id", 0),
                        name=tag.get("name", ""),
                        rank=tag.get("rank", 0),
                        classification=class_name,
                        classification_id=class_id
                    ))
                    total_tags += 1
                
                if tags:
                    classifications.append(TagClassification(
                        id=class_id,
                        name=class_name,
                        tags=tags
                    ))
            
            if classifications:
                groups.append(TagGroup(
                    id=group_id,
                    name=group_name,
                    classifications=classifications
                ))
        
        logger.info(f"获取到 {total_tags} 个标签，{len(groups)} 个分组")
        
        return TagsResponse(groups=groups, total_tags=total_tags)
        
    except requests.RequestException as e:
        logger.error(f"请求 AICoders 失败: {e}")
        raise HTTPException(status_code=502, detail=f"请求 AICoders 失败: {str(e)}")
    except Exception as e:
        logger.error(f"获取标签失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-tag-aicoders", response_model=ProblemListResponse)
async def get_problems_by_tag_aicoders(
    tag_id: int = Query(..., description="标签ID"),
    tag_name: str = Query("", description="标签名称（用于显示）"),
    limit: int = Query(100, ge=1, le=500, description="获取数量"),
    page: int = Query(1, ge=1, description="页码")
):
    """
    按标签ID从 AICoders 获取题目列表
    
    Args:
        tag_id: 标签ID
        tag_name: 标签名称
        limit: 每页数量
        page: 页码
    
    Returns:
        题目列表
    """
    try:
        # AICoders 题目列表 API
        url = f"{AICODERS_API}/api/get-problem-list"
        params = {
            "limit": limit,
            "currentPage": page,
            "tagId": tag_id,
            "keyword": "",
            "difficulty": [],
            "type": 0
        }
        
        logger.info(f"按标签获取题目: tag_id={tag_id}, tag_name={tag_name}")
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        
        if data.get("status") != 200:
            raise HTTPException(status_code=500, detail=f"获取题目失败: {data}")
        
        # 解析题目列表
        problems = []
        records = data.get("data", {}).get("records", [])
        
        for p in records:
            # API 返回 pid 或 problemId，不是 id
            pid = str(p.get("pid") or p.get("problemId") or p.get("id", ""))
            problems.append(ProblemInfo(
                id=pid,
                title=p.get("title", ""),
                url=f"https://oj.aicoders.cn/problem/{pid}",
                source="aicoders"
            ))
        
        total = data.get("data", {}).get("total", len(problems))
        
        logger.info(f"获取到 {len(problems)} 道题目 (总共 {total})")
        
        return ProblemListResponse(total=total, problems=problems)
        
    except requests.RequestException as e:
        logger.error(f"请求 AICoders 失败: {e}")
        raise HTTPException(status_code=502, detail=f"请求 AICoders 失败: {str(e)}")
    except Exception as e:
        logger.error(f"获取题目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-tag", response_model=ProblemListResponse)
async def get_problems_by_tag(
    tag: str = Query(..., description="标签名称"),
    limit: int = Query(100, ge=1, le=500, description="获取数量"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    按标签获取题目列表（SHSOJ）
    
    Args:
        tag: 标签名称
        limit: 获取数量
        offset: 偏移量
    
    Returns:
        题目列表
    """
    try:
        from services.oj.registry import get_global_registry
        from services.unified_config import ConfigManager
        from pathlib import Path
        
        # 获取SHSOJ适配器
        registry = get_global_registry()
        adapter = registry.get_adapter("shsoj")
        
        if not adapter:
            raise HTTPException(status_code=400, detail="SHSOJ适配器未配置")
        
        # 获取题目列表
        fetcher = adapter.get_problem_fetcher()
        if not fetcher or not hasattr(fetcher, 'get_problems_by_tag'):
            raise HTTPException(status_code=400, detail="适配器不支持按标签获取")
        
        problems = fetcher.get_problems_by_tag(tag, limit=limit, offset=offset)
        
        result = [
            ProblemInfo(
                id=str(p.get("id", p.get("pid", ""))),
                title=p.get("title", ""),
                url=p.get("url", f"https://oj.aicoders.cn/problem/{p.get('id', '')}"),
                source="shsoj"
            )
            for p in problems
        ]
        
        logger.info(f"按标签获取题目: tag={tag}, count={len(result)}")
        
        return ProblemListResponse(total=len(result), problems=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取题目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-range", response_model=ProblemListResponse)
async def get_problems_by_range(
    start: int = Query(..., ge=1, description="起始ID"),
    end: int = Query(..., ge=1, description="结束ID"),
    source: str = Query("shsoj", description="来源OJ")
):
    """
    按ID范围获取题目列表
    
    Args:
        start: 起始ID（包含）
        end: 结束ID（包含）
        source: 来源OJ
    
    Returns:
        题目列表
    """
    if end < start:
        raise HTTPException(status_code=400, detail="结束ID必须大于等于起始ID")
    
    if end - start > 500:
        raise HTTPException(status_code=400, detail="范围不能超过500")
    
    try:
        from services.oj.registry import get_global_registry
        
        registry = get_global_registry()
        adapter = registry.get_adapter(source)
        
        if not adapter:
            raise HTTPException(status_code=400, detail=f"适配器不存在: {source}")
        
        # 构造题目列表
        base_url_map = {
            "shsoj": "https://oj.aicoders.cn/problem",
            "luogu": "https://www.luogu.com.cn/problem",
        }
        
        base_url = base_url_map.get(source, "")
        
        problems = []
        for pid in range(start, end + 1):
            problems.append(ProblemInfo(
                id=str(pid),
                title=None,  # 需要单独拉取
                url=f"{base_url}/{pid}" if base_url else str(pid),
                source=source
            ))
        
        logger.info(f"按范围生成题目列表: {start}-{end}, source={source}, count={len(problems)}")
        
        return ProblemListResponse(total=len(problems), problems=problems)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取题目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ManualProblemRequest(BaseModel):
    """手动创建题目请求"""
    custom_id: str
    title: str
    description: str
    input_format: Optional[str] = ""
    output_format: Optional[str] = ""
    samples: Optional[str] = ""
    constraints: Optional[str] = ""
    time_limit: int = 1000
    memory_limit: int = 256


@router.post("/create-manual")
async def create_manual_problem(
    request: ManualProblemRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    手动创建题目（从粘贴的题面）
    
    Args:
        request: 题目数据
        current_user: 当前用户
    
    Returns:
        创建结果
    """
    try:
        from pathlib import Path
        import json
        
        # 创建用户隔离的工作目录（支持环境变量）
        import os
        user_id = current_user["user_id"]
        workspace_base = os.getenv("OJO_WORKSPACE")
        if not workspace_base:
            docker_workspace = Path("/app/workspace")
            if docker_workspace.exists():
                workspace_base = str(docker_workspace)
            else:
                workspace_base = "workspace"
        workspace = Path(workspace_base) / f"user_{user_id}"
        problem_dir = workspace / f"problem_{request.custom_id}"
        problem_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建problem_data.json
        problem_data = {
            "id": request.custom_id,
            "title": request.title,
            "description": request.description,
            "input_format": request.input_format,
            "output_format": request.output_format,
            "samples": request.samples,
            "constraints": request.constraints,
            "time_limit": request.time_limit,
            "memory_limit": request.memory_limit,
            "source": "manual",
            "examples": []
        }
        
        # 解析样例
        if request.samples:
            lines = request.samples.strip().split('\n')
            in_input = False
            in_output = False
            current_input = []
            current_output = []
            
            for line in lines:
                lower = line.lower().strip()
                if '输入' in lower or 'input' in lower:
                    if current_input and current_output:
                        problem_data["examples"].append({
                            "input": '\n'.join(current_input),
                            "output": '\n'.join(current_output)
                        })
                        current_input = []
                        current_output = []
                    in_input = True
                    in_output = False
                elif '输出' in lower or 'output' in lower:
                    in_input = False
                    in_output = True
                elif in_input:
                    current_input.append(line)
                elif in_output:
                    current_output.append(line)
            
            # 添加最后一组样例
            if current_input or current_output:
                problem_data["examples"].append({
                    "input": '\n'.join(current_input),
                    "output": '\n'.join(current_output)
                })
        
        # 保存
        json_path = problem_dir / "problem_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(problem_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"手动创建题目: {request.custom_id}, path={problem_dir}")
        
        return {
            "success": True,
            "problem_id": request.custom_id,
            "path": str(problem_dir),
            "message": "题目创建成功"
        }
        
    except Exception as e:
        logger.error(f"创建题目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/identify")
async def identify_problem_source(url: str = Query(..., description="题目URL或ID")):
    """
    识别题目来源OJ
    
    Args:
        url: 题目URL或ID
    
    Returns:
        识别结果
    """
    try:
        from services.oj.registry import get_global_registry
        
        registry = get_global_registry()
        adapter = registry.find_adapter_by_url(url)
        
        if adapter:
            fetcher = adapter.get_problem_fetcher()
            parsed_id = fetcher.parse_problem_id(url) if fetcher else None
            
            return {
                "identified": True,
                "source": adapter.name,
                "display_name": adapter.display_name,
                "parsed_id": parsed_id,
                "original": url
            }
        
        # 尝试识别纯数字ID
        if url.strip().isdigit():
            return {
                "identified": True,
                "source": "shsoj",  # 默认
                "display_name": "SHSOJ",
                "parsed_id": url.strip(),
                "original": url
            }
        
        return {
            "identified": False,
            "source": None,
            "original": url
        }
        
    except Exception as e:
        logger.error(f"识别题目来源失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
