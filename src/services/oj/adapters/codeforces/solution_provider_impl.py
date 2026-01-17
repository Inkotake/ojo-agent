# -*- coding: utf-8 -*-
"""Codeforces官方题解获取实现（骨架）"""

from typing import Dict, Any, Optional
from ...base.solution_provider import SolutionProvider


class CodeforcesSolutionProvider(SolutionProvider):
    """Codeforces官方题解提供器（Tutorial）"""
    
    def __init__(self):
        self.timeout = 30
    
    def has_official_solution(self, problem_id: str) -> bool:
        """判断是否有官方题解
        
        Codeforces通常在比赛结束后发布Tutorial
        """
        """Return whether an official tutorial exists for a given problem.

        On Codeforces an editorial is typically published as a blog post
        after a contest ends.  While there is no guaranteed mapping
        between a contest ID and a blog entry ID, many contest
        editorials can be found at either

            https://codeforces.com/contest/{contest_id}/editorial

        or

            https://codeforces.com/blog/entry/{contest_id}

        This method attempts to perform a lightweight HTTP GET to
        determine if either location is reachable (HTTP status 200).
        If a request fails or returns a non‑200 status code the
        method assumes no official editorial is available.

        Args:
            problem_id: A Codeforces problem identifier such as
                ``1234A``.

        Returns:
            True if an editorial URL appears to be reachable, False
            otherwise.
        """
        import re
        import requests
        # Extract the numeric contest ID from the problem ID.  The
        # problem_id is of the form ``{contest_id}{index}``, e.g.
        # ``1234A``.  We strip trailing letters to get the contest ID.
        m = re.match(r'^(\d+)', problem_id)
        if not m:
            return False
        contest_id = m.group(1)
        # Candidate URLs to check for an editorial
        candidates = [
            f"https://codeforces.com/contest/{contest_id}/editorial",
            f"https://codeforces.com/blog/entry/{contest_id}"
        ]
        for url in candidates:
            try:
                resp = requests.get(url, timeout=self.timeout)
                # Some blog pages return a 200 with a minimal body even if
                # the entry does not exist (Codeforces renders an error
                # message).  We simply treat any 200 as an existing
                # editorial, leaving deeper validation to fetch_solution().
                if resp.status_code == 200:
                    return True
            except Exception:
                continue
        return False
    
    def fetch_solution(self, problem_id: str) -> Optional[Dict[str, Any]]:
        """获取Codeforces官方题解
        
        Args:
            problem_id: 题目ID（如1234A）
            
        Returns:
            题解数据
        """
        """Fetch the official editorial for a Codeforces problem.

        This method first derives the contest ID from the given
        problem identifier (e.g. ``1234`` from ``1234A``).  It then
        attempts to download the editorial from two common locations:

            1. ``https://codeforces.com/contest/{contest_id}/editorial``
            2. ``https://codeforces.com/blog/entry/{contest_id}``

        If a page is successfully retrieved (HTTP 200) its title and
        main content are parsed using BeautifulSoup.  The content is
        returned in the ``content`` field of the result.  In the event
        that neither location is reachable the method returns a
        fallback dictionary with a link to the presumed blog entry.

        Args:
            problem_id: A Codeforces problem identifier such as
                ``1234A``.

        Returns:
            A dictionary describing the editorial, or None if no
            editorial could be found.
        """
        import re
        import requests
        from bs4 import BeautifulSoup
        # Extract contest ID and problem index
        m = re.match(r'^(\d+)([A-Z]\d?)$', problem_id)
        if not m:
            raise ValueError(f"Invalid Codeforces problem id: {problem_id}")
        contest_id = m.group(1)
        # Candidate URLs in order of preference
        candidates = [
            f"https://codeforces.com/contest/{contest_id}/editorial",
            f"https://codeforces.com/blog/entry/{contest_id}"
        ]
        for url in candidates:
            try:
                resp = requests.get(url, timeout=self.timeout)
                if resp.status_code != 200:
                    continue
                # Parse the editorial page
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Title: try to take from the page title, otherwise
                # synthesise one
                page_title = soup.title.get_text(strip=True) if soup.title else f"Problem {problem_id} Tutorial"
                # Try to locate the main content of the blog/editorial.
                # Codeforces blog entries typically wrap the body in a
                # ``div`` with class ``ttypography``.  For contest
                # editorials this may differ, so we fall back to using
                # the full text of the page if necessary.
                content_div = soup.find('div', class_='ttypography') or soup.find('div', class_='entry-content')
                if content_div:
                    content_text = content_div.get_text(separator='\n').strip()
                else:
                    # As a fallback use the complete text of the page
                    content_text = soup.get_text(separator='\n').strip()
                return {
                    "problem_id": problem_id,
                    "source": "official",
                    "title": page_title,
                    "content": content_text,
                    "author": "Codeforces Editorial",
                    "language": "en",
                    "url": url,
                    "code_samples": [],
                    "algorithm": "",
                    "complexity": {}
                }
            except Exception:
                continue
        # Fallback: return a minimal result pointing at the presumed blog
        # entry.  This allows callers to at least locate the editorial
        # manually when automatic retrieval fails.
        fallback_url = f"https://codeforces.com/blog/entry/{contest_id}"
        return {
            "problem_id": problem_id,
            "source": "official",
            "title": f"Problem {problem_id} Tutorial",
            "content": f"The official editorial for contest {contest_id} could not be automatically retrieved."
                       f" Please see {fallback_url}",
            "author": "Codeforces Editorial",
            "language": "en",
            "url": fallback_url,
            "code_samples": [],
            "algorithm": "",
            "complexity": {}
        }

