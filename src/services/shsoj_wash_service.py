from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
import json

from loguru import logger

from services.unified_config import AppConfig, ConfigManager
from services.oj_api import OJApi, OJAuth
from utils.concurrency import CancelToken, retry_with_backoff
from wash import prepare_update_payload as cli_prepare_update_payload


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
DEFAULT_FIELDS: Sequence[str] = (
    "title",
    "description",
    "input",
    "output",
    "examples",
    "hint",
    "source",
    "remark",
)
DEFAULT_KEYWORDS: Sequence[str] = ("童程同美",)


@dataclass
class WashStats:
    scanned: int = 0
    fetched: int = 0
    matched: int = 0
    updated: int = 0
    failures: int = 0


@dataclass
class WashTaskConfig:
    start: int = 1
    end: int = 20000
    keywords: Sequence[str] = DEFAULT_KEYWORDS
    replacement: str = "李华"
    fields: Sequence[str] = DEFAULT_FIELDS
    dry_run: bool = True
    delay: float = 0.2
    max_failures: int = 50
    workers: int = 4
    verbose: bool = False


@dataclass
class WashProblemResult:
    pid: int
    changes: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None


def sanitize_text(value: str, keywords: Sequence[str], replacement: str) -> Tuple[str, int]:
    total_hits = 0
    text = value
    for kw in keywords:
        if not kw:
            continue
        count = text.count(kw)
        if count:
            text = text.replace(kw, replacement)
            total_hits += count
    return text, total_hits


def sanitize_problem_payload(
    payload: Dict[str, object],
    keywords: Sequence[str],
    replacement: str,
    fields: Sequence[str],
) -> Dict[str, int]:
    target = payload.get("problem")
    if not isinstance(target, dict):
        target = payload

    changes: Dict[str, int] = {}
    for field in fields:
        original = target.get(field)
        if isinstance(original, str):
            new_text, hits = sanitize_text(original, keywords, replacement)
            if hits:
                target[field] = new_text
                changes[field] = hits
    return changes


class SHSOJWashService:
    def __init__(self, cfg_mgr: ConfigManager):
        self.cfg_mgr = cfg_mgr
        self._executor: Optional[ThreadPoolExecutor] = None
        self._cancel = CancelToken()
        self._lock = threading.Lock()

    def stop(self) -> None:
        self._cancel.cancel()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    @staticmethod
    def run_self_tests() -> None:
        sample_payload = {
            "problem": {
                "title": "Sample 童程同美 title",
                "description": "No keyword here",
                "examples": "First 童程同美 example, second 童程同美 example",
            }
        }
        changes = sanitize_problem_payload(
            sample_payload,
            keywords=("童程童美", "童程", "童童"),
            replacement="李华",
            fields=("title", "description", "examples"),
        )
        assert changes["title"] == 1
        assert changes["examples"] == 2
        assert "description" not in changes

    def run(
        self,
        task_cfg: WashTaskConfig,
        *,
        on_log=None,
        on_progress=None,
        on_problem=None,
    ) -> None:
        if not self.cfg_mgr:
            raise RuntimeError("未设置 ConfigManager")
        stats = WashStats()
        cfg = self.cfg_mgr.cfg
        base_url, username, password = self._resolve_credentials(cfg)
        proxies = self._resolve_proxies(cfg)
        verify_ssl = getattr(cfg, "verify_ssl", True)

        def _log(msg: str) -> None:
            if on_log is not None:
                try:
                    on_log(msg)
                    return
                except Exception:
                    logger.debug("wash on_log callback failed", exc_info=True)
            logger.info(msg)

        api = OJApi(base_url=base_url, timeout=30, proxies=proxies or None, verify_ssl=verify_ssl)
        _log(f"正在登录 SHSOJ（{base_url}）...")
        auth = retry_with_backoff(
            lambda: api.login_user(username, password),
            max_attempts=5,
            base_delay=2.0,
            factor=1.5,
            on_error=lambda exc, attempt: _log(f"登录失败（第 {attempt} 次）: {exc}"),
        )

        keywords = tuple(kw.strip() for kw in task_cfg.keywords if kw.strip())
        if not keywords:
            keywords = DEFAULT_KEYWORDS
        fields = tuple(field.strip() for field in task_cfg.fields if field.strip())
        pids = list(range(task_cfg.start, task_cfg.end + 1))
        stats.scanned = len(pids)
        self.stop()
        self._cancel = CancelToken()
        self._executor = ThreadPoolExecutor(max_workers=max(1, task_cfg.workers))

        futures: Dict[Future, int] = {}
        for pid in pids:
            if self._cancel.cancelled():
                break
            futures[self._executor.submit(self._fetch_and_sanitize, api, auth, pid, keywords, task_cfg, fields)] = pid

        consecutive_failures = 0
        for future in as_completed(futures):
            pid = futures[future]
            if self._cancel.cancelled():
                break
            try:
                payload, changes = future.result()
            except Exception as exc:
                stats.failures += 1
                consecutive_failures += 1
                if on_problem:
                    on_problem(WashProblemResult(pid=pid, error=str(exc)))
                _log(f"题目 {pid} 处理失败：{exc}")
                if consecutive_failures >= task_cfg.max_failures:
                    _log("连续失败次数过多，自动停止。")
                    break
                continue

            if payload is None:
                continue

            stats.fetched += 1
            if changes:
                stats.matched += 1
                if on_problem is not None:
                    try:
                        on_problem(WashProblemResult(pid=pid, changes=changes))
                    except Exception:
                        logger.debug("wash on_problem callback failed", exc_info=True)
                _log(
                    f"题目 {pid} 捕获关键词，字段："
                    + ", ".join(f"{k}:{v}" for k, v in changes.items())
                )
                if not task_cfg.dry_run:
                    include_cases = False
                    try:
                        raw_cases = api.fetch_problem_cases(auth, pid)
                        if raw_cases:
                            from wash import normalize_test_cases  # 复用 CLI 逻辑

                            normalized_cases = normalize_test_cases(pid, raw_cases)
                            if normalized_cases:
                                payload["testCaseScore"] = normalized_cases
                                payload["samples"] = normalized_cases
                                include_cases = True
                                _log(
                                    f"题目 {pid} 从服务器加载 {len(normalized_cases)} 个测试用例用于更新。"
                                )
                        else:
                            _log(
                                f"题目 {pid} 获取测试用例为空，为避免丢失数据，本次更新将跳过该题。"
                            )
                    except Exception as exc:  # noqa: PIE786
                        _log(
                            f"题目 {pid} 获取测试用例失败({exc})，为避免丢失数据，本次更新将跳过该题。"
                        )

                    if not include_cases:
                        # 不更新该题，保护现有测试数据
                        continue

                    try:
                        update_payload = self._prepare_update_payload(
                            payload, include_cases=include_cases
                        )
                        api.put_admin_problem(auth, update_payload)
                        stats.updated += 1
                        _log(f"题目 {pid} 更新成功。")
                    except Exception as exc:  # noqa: PIE786
                        stats.failures += 1
                        consecutive_failures += 1
                        if on_problem is not None:
                            try:
                                on_problem(WashProblemResult(pid=pid, error=str(exc)))
                            except Exception:
                                logger.debug("wash on_problem callback failed", exc_info=True)
                        _log(f"题目 {pid} 更新失败：{exc}")
                        if consecutive_failures >= task_cfg.max_failures:
                            _log("连续失败次数过多，自动停止。")
                            break
                        continue
            if on_progress is not None:
                try:
                    on_progress(stats)
                except Exception:
                    logger.debug("wash on_progress callback failed", exc_info=True)
            consecutive_failures = 0

        self.stop()
        if on_progress is not None:
            try:
                on_progress(stats)
            except Exception:
                logger.debug("wash on_progress callback failed", exc_info=True)

    def _resolve_proxies(self, cfg: AppConfig) -> Dict[str, str]:
        if getattr(cfg, "proxy_enabled", False):
            if cfg.http_proxy or cfg.https_proxy:
                return {
                    "http": cfg.http_proxy or cfg.https_proxy,
                    "https": cfg.https_proxy or cfg.http_proxy,
                }
        return {}

    def _resolve_credentials(self, cfg: AppConfig) -> Tuple[str, str, str]:
        adapter_cfg: Dict[str, str] = {}
        if isinstance(cfg.adapter_configs, dict):
            adapter_cfg = cfg.adapter_configs.get("shsoj", {}) or {}

        base_url = adapter_cfg.get("base_url") or cfg.oj_base_url or "https://oj.shsbnu.net"
        base_url = self._normalize_frontend_url(base_url)
        username = adapter_cfg.get("username") or cfg.oj_username
        password = adapter_cfg.get("password") or cfg.oj_password

        if not username or not password:
            raise RuntimeError("配置中缺少 SHSOJ 登录凭证。")

        return base_url.rstrip("/"), username, password

    def _normalize_frontend_url(self, url: str) -> str:
        if not url:
            return "https://oj.shsbnu.net"

        url = url.rstrip("/")
        lower = url.lower()

        if "oj-api.shsbnu.net" in lower:
            return "https://oj.shsbnu.net"

        if "api-tcoj.aicoders.cn" in lower:
            return "https://oj.aicoders.cn"

        return url

    def _prepare_update_payload(
        self, flat_payload: Dict[str, object], *, include_cases: bool = False
    ) -> Dict[str, object]:
        """直接复用 wash.py 的实现，保证与 CLI wash 行为一致"""
        return cli_prepare_update_payload(flat_payload, include_cases=include_cases)

    def _fetch_and_sanitize(
        self,
        api: OJApi,
        auth: OJAuth,
        pid: int,
        keywords: Sequence[str],
        task_cfg: WashTaskConfig,
        fields: Sequence[str],
    ) -> Tuple[Optional[Dict[str, object]], Dict[str, int]]:
        if self._cancel.cancelled():
            return None, {}
        payload = api.fetch_admin_problem(auth, pid)
        if task_cfg.delay > 0:
            time.sleep(task_cfg.delay)
        if not payload:
            return None, {}
        changes = sanitize_problem_payload(payload, keywords, task_cfg.replacement, fields)
        return payload, changes


__all__ = [
    "SHSOJWashService",
    "WashTaskConfig",
    "WashStats",
    "WashProblemResult",
    "DEFAULT_FIELDS",
    "DEFAULT_KEYWORDS",
]

