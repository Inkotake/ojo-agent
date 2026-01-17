# -*- coding: utf-8 -*-
"""AtCoder题面获取实现（骨架）"""
from typing import Dict, Any, Optional
import re
from ...base.problem_fetcher import ProblemFetcher

class AtCoderProblemFetcher(ProblemFetcher):
    def supports_url(self, url: str) -> bool:
        return 'atcoder.jp' in url.lower()
    
    def parse_problem_id(self, input_str: str) -> Optional[str]:
        # 支持: abc300_a, https://atcoder.jp/contests/abc300/tasks/abc300_a
        if match := re.search(r'/tasks/([a-z]+\d+_[a-z]\d?)', input_str):
            return match.group(1)
        elif re.match(r'^[a-z]+\d+_[a-z]\d?$', input_str):
            return input_str
        return None
    
    def fetch_problem(self, problem_id: str) -> Dict[str, Any]:
        """Fetch AtCoder problem statement.

        AtCoder problems live under the URL pattern
        ``https://atcoder.jp/contests/{contest}/tasks/{problem_id}``.  The
        ``problem_id`` provided to this method already includes the contest
        identifier (for example ``abc300_a``).  This implementation will
        attempt to download the problem page, parse the statement, input
        format, output format and sample tests and return them in a
        structured dictionary.

        We favour the English translation where available by appending
        ``?lang=en`` to the URL.  If an English version cannot be found
        the Japanese statement will be used instead.  Time and memory
        limits are extracted when present.

        Args:
            problem_id: An AtCoder task identifier such as ``abc300_a``.

        Returns:
            A dictionary conforming to the ProblemFetcher contract.

        Raises:
            RuntimeError: If the problem page cannot be fetched or parsed.
        """
        # Derive the contest identifier from the problem ID.  The
        # problem_id is of the form ``{contest}_{taskletter}``, e.g.
        # ``abc300_a``.  Everything before the last underscore is the
        # contest ID.
        if '_' not in problem_id:
            raise ValueError(f"Invalid AtCoder problem id: {problem_id}")
        contest = problem_id.rsplit('_', 1)[0]
        # Construct the URL and prefer English when available.
        url = f"https://atcoder.jp/contests/{contest}/tasks/{problem_id}?lang=en"

        try:
            import requests
            from bs4 import BeautifulSoup
            # Fetch the page.  If the request fails we allow the
            # exception to propagate so the caller can decide how to
            # handle it.
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            # Provide a clear error message rather than leaking a raw
            # requests exception.  Retain the original exception as
            # context.
            raise RuntimeError(f"Failed to fetch AtCoder problem page: {e}") from e

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extract time and memory limits if available.  These values
        # appear near the top of the page in a paragraph like
        # ``Time Limit: 2 sec / Memory Limit: 1024 MiB``.  We extract
        # numeric parts using regular expressions.  Time limit is
        # reported in seconds and converted to milliseconds.
        import re
        time_limit_ms: Optional[int] = None
        memory_limit_mb: Optional[int] = None
        page_text = soup.get_text(separator='\n')
        m = re.search(r'Time Limit:\s*([\d.]+)\s*sec', page_text)
        if m:
            try:
                time_limit_ms = int(float(m.group(1)) * 1000)
            except ValueError:
                time_limit_ms = None
        # 支持MB和GB单位
        m = re.search(r'Memory Limit:\s*([\d.]+)\s*(M|G)(i|)B', page_text, re.IGNORECASE)
        if m:
            try:
                mem_value = float(m.group(1))
                unit = m.group(2).upper()
                if unit == 'G':
                    memory_limit_mb = int(mem_value * 1024)  # GB转MB
                else:
                    memory_limit_mb = int(mem_value)
            except ValueError:
                memory_limit_mb = None

        # Find the task statement container.  The statement is wrapped
        # inside a div with id ``task-statement``.  Within this div
        # there is typically a ``span.lang`` containing two child
        # spans: ``lang-ja`` (Japanese) and ``lang-en`` (English).  We
        # prefer the English version if present; otherwise we fall back
        # to whatever language is available.  As a final fallback, if
        # the language wrapper cannot be found we operate on the
        # original statement div directly.
        statement_div = soup.find(id='task-statement')
        if not statement_div:
            raise RuntimeError("Failed to locate task statement on AtCoder page")
        lang_span = None
        # Attempt to locate language specific spans
        wrapper = statement_div.find('span', class_='lang')
        if wrapper:
            lang_span = wrapper.find('span', class_='lang-en') or wrapper.find('span', class_='lang-ja')
        if not lang_span:
            # Fallback: use entire statement div
            lang_span = statement_div

        # Parse the individual sections of the statement.  The page
        # organizes content into ``div.part`` elements each containing
        # a ``section`` with an ``h3`` heading and the associated
        # content.  Headings we care about include
        # "Problem Statement", "Input", "Output" (English) and their
        # Japanese equivalents.  Sample inputs and outputs are also
        # headed by "Sample Input" / "Sample Output" or
        # "入力例" / "出力例".  We collect sample inputs and outputs
        # separately and pair them by index.
        description = ""
        input_format = ""
        output_format = ""
        sample_inputs: list[str] = []
        sample_outputs: list[str] = []

        parts = lang_span.find_all('div', class_='part')
        for part in parts:
            # Each part contains a section; proceed only if we have
            # both a heading and some content.  We strip leading and
            # trailing whitespace and normalise the case for matching.
            section = part.find('section')
            if not section:
                continue
            heading_tag = section.find('h3')
            if not heading_tag:
                continue
            heading = heading_tag.get_text().strip().lower()
            # Retrieve the text content excluding the heading itself.
            # This yields all paragraphs and preformatted blocks.
            # We remove the heading text from the start of the full
            # section text to avoid duplication.
            section_text = section.get_text().strip()
            # Remove the heading text if it appears at the start
            if section_text.lower().startswith(heading):
                section_text = section_text[len(heading):].strip()

            # Classify the section
            if ('problem statement' in heading) or ('問題文' in heading):
                description = section_text
            elif ('input' in heading) or ('入力' in heading):
                input_format = section_text
            elif ('output' in heading) or ('出力' in heading):
                output_format = section_text
            elif ('sample input' in heading) or ('入力例' in heading):
                pre = section.find('pre')
                if pre:
                    sample_inputs.append(pre.get_text().strip())
            elif ('sample output' in heading) or ('出力例' in heading):
                pre = section.find('pre')
                if pre:
                    sample_outputs.append(pre.get_text().strip())

        # Pair up sample inputs and outputs.  Some problems may have
        # unequal numbers of sample inputs and outputs; we zip them so
        # pairs are aligned in order.  Any extras are discarded.
        samples = []
        for inp, out in zip(sample_inputs, sample_outputs):
            samples.append({"input": inp, "output": out})

        # Build the return dictionary.  Fields not provided by
        # AtCoder (such as difficulty, tags, hints, author) are set to
        # None or empty lists.  We include the original URL for
        # reference and store the contest id in ``extra`` for
        # potential downstream use.
        result: Dict[str, Any] = {
            "id": problem_id,
            "source": "atcoder",
            "title": soup.title.string.strip() if soup.title else problem_id,
            "description": description,
            "input_format": input_format,
            "output_format": output_format,
            "samples": samples,
            "time_limit": time_limit_ms,
            "memory_limit": memory_limit_mb,
            "difficulty": None,
            "tags": [],
            "hints": None,
            "author": None,
            "url": url,
            "extra": {
                "oj_type": "atcoder",
                "contest_id": contest
            }
        }

        return result

