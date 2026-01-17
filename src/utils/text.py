# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import re
from bs4 import BeautifulSoup


def _collapse_underscores(value: str) -> str:
    """合并连续下划线为单个（内部辅助）"""
    return re.sub(r'_+', '_', value)


def _strip_edge_underscores(value: str) -> str:
    """移除开头和结尾的下划线（内部辅助）"""
    return value.strip('_')


def sanitize_filename(filename: str) -> str:
    """将URL或字符串转换为安全的文件名（Windows兼容）"""
    # 替换所有非法字符为下划线
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 移除连续的下划线
    safe_name = _collapse_underscores(safe_name)
    # 移除开头和结尾的下划线
    safe_name = _strip_edge_underscores(safe_name)
    # 限制长度
    if len(safe_name) > 50:
        safe_name = safe_name[:50]
    return safe_name


def samples_to_xml(samples: list) -> str:
    """将样例列表转换为XML格式字符串
    
    Args:
        samples: 样例列表，每个元素为 {"input": "...", "output": "..."}
        
    Returns:
        XML格式字符串，如 "<input>1 2</input><output>3</output>"
    """
    if not samples:
        return ""
    
    examples_parts = []
    for sample in samples:
        # 输入：strip 掉首尾空白（通常输入格式要求严格）
        inp = sample.get("input", "").strip()
        # 输出：只 strip 尾随空白，保留前导空白（字符串图案题需要前导空格）
        out = sample.get("output", "")
        out_lines = out.split('\n')
        # 去掉首尾的空白行
        while out_lines and not out_lines[0].strip():
            out_lines.pop(0)
        while out_lines and not out_lines[-1].strip():
            out_lines.pop()
        # 每行只去掉尾随空白，保留前导空白
        out_cleaned = '\n'.join(line.rstrip() for line in out_lines)
        examples_parts.append(f"<input>{inp}</input>")
        examples_parts.append(f"<output>{out_cleaned}</output>")
    return "\n".join(examples_parts)


def samples_to_problem_format(samples: list, hints: any = None) -> dict:
    """将适配器返回的样例格式转换为 GeneratorService/SolveService 期望的格式
    
    Args:
        samples: 样例列表，每个元素为 {"input": "...", "output": "..."}
        hints: 提示信息（字符串或列表）
        
    Returns:
        转换后的字典，包含 examples 字段
    """
    examples_text = samples_to_xml(samples) if samples else ""
    
    # 处理hints格式（可能是字符串或列表）
    if isinstance(hints, list):
        hints_text = "\n".join(str(h) for h in hints)
    elif hints:
        hints_text = str(hints)
    else:
        hints_text = ""
    
    return {
        "examples": examples_text,
        "samples": samples,
        "hint": hints_text,
    }


def parse_examples(examples_html: str) -> str:
    """解析样例，分离输入和输出"""
    if not examples_html:
        return ""
    
    # 尝试解析XML格式的样例 <input>...</input><output>...</output>
    input_match = re.findall(r'<input>(.*?)</input>', examples_html, re.DOTALL)
    output_match = re.findall(r'<output>(.*?)</output>', examples_html, re.DOTALL)
    
    if input_match and output_match:
        # 找到了结构化的输入输出
        result_parts = []
        for i, (inp, out) in enumerate(zip(input_match, output_match), 1):
            result_parts.append(f"**样例 {i}**")
            result_parts.append(f"输入：")
            # 输入：strip 掉首尾空白（通常输入格式要求严格）
            result_parts.append(inp.strip())
            result_parts.append(f"输出：")
            # 输出：只 strip 尾随空白，保留前导空白（字符串图案题需要前导空格）
            # 但要去掉整个输出的首尾空白行
            out_lines = out.split('\n')
            # 去掉首尾的空白行
            while out_lines and not out_lines[0].strip():
                out_lines.pop(0)
            while out_lines and not out_lines[-1].strip():
                out_lines.pop()
            # 每行只去掉尾随空白，保留前导空白
            out_cleaned = '\n'.join(line.rstrip() for line in out_lines)
            result_parts.append(out_cleaned)
            result_parts.append("")
        return "\n".join(result_parts)
    else:
        # 没有结构化格式，直接返回纯文本
        return html_to_text(examples_html)


def html_to_text(html_str: str) -> str:
    soup = BeautifulSoup(html_str or "", "html.parser")
    
    # 将 <img> 标签转换为 Markdown 格式，保留图片信息
    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "image")
        if src:
            # 将 <img> 替换为 Markdown 格式 ![alt](src)
            img.replace_with(f"![{alt}]({src})")
    
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all("p"):
        p.insert_after(soup.new_string("\n"))
    text = soup.get_text()
    return html.unescape(text).strip()


def sanitize_cpp_code(raw_code: str) -> str:
    """清洗C++代码，移除markdown标记和LLM解释文字"""
    code = raw_code.strip()
    
    # 移除markdown代码块标记
    code = re.sub(r'```(?:cpp|c\+\+|c)?\s*\n?', '', code, flags=re.IGNORECASE)
    code = re.sub(r'```\s*$', '', code)
    
    lines = code.splitlines()
    cleaned_lines = []
    skip_until_code = True
    
    # LLM常见的解释文字模式
    explanation_patterns = [
        'method explanation', 'elegant explanation', 'explanation of', 'approach',
        'the problem', 'dp state', 'algorithm', 'solution explanation',
        'this problem', 'we can solve', 'the key', 'the idea',
        'step 1:', 'step 2:', 'first,', 'second,', 'finally,',
        '###', '##', '**', 'note:', 'here is', 'below is'
    ]
    
    for line in lines:
        stripped = line.strip()
        
        if skip_until_code:
            # 找到第一行真正的C++代码
            if (stripped.startswith('#include') or 
                stripped.startswith('using namespace') or
                stripped.startswith('int main') or
                stripped.startswith('void ') or
                stripped.startswith('class ') or
                stripped.startswith('struct ') or
                stripped.startswith('typedef ') or
                stripped.startswith('namespace ')):
                skip_until_code = False
                cleaned_lines.append(line)
            # 跳过LLM的解释文字
            elif any(pattern in stripped.lower() for pattern in explanation_patterns):
                continue
            # 跳过空行和只有标点的行
            elif not stripped or stripped in ['```', '---', '===']:
                continue
        else:
            # 移除 [代码] 标记
            line = re.sub(r'^\[\u4ee3\u7801\]\s*', '', line)
            line = re.sub(r'^\[代码\]\s*', '', line)
            cleaned_lines.append(line)
    
    code = '\n'.join(cleaned_lines)
    
    # 移除多余的空行
    code = re.sub(r'\n{3,}', '\n\n', code)
    
    return code.strip()

def sanitize_code(raw_code: str, problem_id: str) -> str:
    code = raw_code.strip()
    
    # Remove markdown fences (prefer the largest code block if multiple exist)
    fences = re.findall(r"```(?:\w+)?\s*(.*?)\s*```", code, flags=re.DOTALL)
    if fences:
        # 选择最长的代码块，避免拿到被截断的示例或说明片段
        code = max(fences, key=len).strip()
    
    # Remove system prompt patterns (common LLM contamination)
    # Define comprehensive system prompt patterns to filter
    system_prompt_patterns = [
        'you are', 'an expert', 'a professional', 'you create', 
        'you have', 'your task', 'your goal', 'you will',
        'test case generator', 'competitive programming', 'edge-case-rich',
        'validates algorithmic solutions', 'comprehensive',
        'here is', 'here\'s', 'below is', 'following is',
        'this code', 'this script', 'the code', 'the script',
        'generates test', 'creates test', 'produces test'
    ]
    
    # Patterns to remove completely
    remove_patterns = [
        r'^\[思考\]',  # [思考] 标记
        r'^\[代码\]',  # [代码] 标记
        r'^#+\s',      # Markdown标题 (###, ##, #)
        r'^\*\*.*?\*\*',  # Markdown粗体
        r'^---+\s*$',  # 分隔线
        r'^===+\s*$',  # 分隔线
    ]
    
    lines = code.splitlines()
    cleaned_lines = []
    skip_until_code = True
    
    for line in lines:
        stripped = line.strip()
        
        # 检查是否需要完全移除此行
        should_remove = any(re.match(pattern, stripped) for pattern in remove_patterns)
        if should_remove:
            continue
        
        # Skip system prompts and instructions
        if skip_until_code:
            # Check if this is actual code (imports, PROBLEM_ID, etc.)
            if (stripped.startswith('#') and 'coding' in stripped) or \
               stripped.startswith('import ') or \
               stripped.startswith('from ') or \
               'PROBLEM_ID' in stripped or \
               stripped.startswith('def ') or \
               stripped.startswith('class '):
                skip_until_code = False
                cleaned_lines.append(line)
            else:
                # Skip lines containing system prompt patterns
                contains_prompt = any(pattern in stripped.lower() for pattern in system_prompt_patterns)
                if not contains_prompt and stripped and not stripped.startswith('```'):
                    # This might be a valid line, but be conservative
                    cleaned_lines.append(line)
        else:
            # After we found code, keep everything except markdown fences
            if not stripped.startswith('```'):
                cleaned_lines.append(line)
    
    code = '\n'.join(cleaned_lines)
    
    # 替换全角字符（逐个替换以避免maketrans问题）
    replacements = [
        ('：', ':'), ('（', '('), ('）', ')'), ('，', ','),
        ('；', ';'), ('。', '.'), ('！', '!'), ('【', '['),
        ('】', ']'),
    ]
    for old_char, new_char in replacements:
        code = code.replace(old_char, new_char)
    
    # 处理引号（可能有编码问题的字符）
    # 中文双引号
    code = code.replace('"', '"').replace('"', '"')
    # 中文单引号
    code = code.replace(''', "'").replace(''', "'")
    
    # 修复常见的zip路径f-string错误：
    # 1. 将不含{}插值的f-string降级为普通字符串
    #    如：f"problem_xxx_testcase.zip" -> "problem_xxx_testcase.zip"
    code = re.sub(r'\bf"([^{}"]+)"', r'"\1"', code)
    
    # 2. 修复缺少右花括号的 f-string：f"problem_{xxx_testcase.zip" -> "problem_{xxx}_testcase.zip"
    #    匹配模式：f"problem_{后面没有}直接跟_testcase.zip
    code = re.sub(
        r'\bf"(problem_)\{([^}]+)(_testcase\.zip)"',
        r'f"\1{\2}\3"',
        code
    )
    
    # 3. 修复完全错误的格式：f"problem_{safe_problem_xxx_testcase.zip" 
    #    这种情况直接用变量名构造正确的 f-string
    code = re.sub(
        r'\bf"problem_\{safe_([^_}]+)_testcase\.zip"',
        r'f"problem_{safe_\1}_testcase.zip"',
        code
    )
    
    # 4. 移除 tests 目录清理代码（避免打包前删除文件）
    #    改为用 pass 替换，避免留下空块导致 IndentationError
    code = re.sub(
        r'(\n\s*)shutil\.rmtree\s*\(\s*OUT_DIR\s*\)',
        r'\1pass  # 保留 tests 目录供后续打包',
        code
    )
    code = re.sub(
        r'(\n\s*)shutil\.rmtree\s*\(\s*["\']tests["\']\s*\)',
        r'\1pass  # 保留 tests 目录供后续打包',
        code
    )

    # Ensure proper encoding header
    if not code.startswith("# -*- coding: utf-8 -*-"):
        code = "# -*- coding: utf-8 -*-\n" + code
    
    # 强制题号（使用规范化ID：适配器+ID格式）
    # problem_id参数传入的是规范化ID（如 luogu_B4071），用于prompt显示
    code = re.sub(r"PROBLEM_ID\s*=\s*['\"].*?['\"]", f'PROBLEM_ID = "{problem_id}"', code)
    
    # 强制压缩包名（使用完整URL安全化格式）
    # 注意：这里需要从上下文中获取original_id，但sanitize_code没有这个参数
    # 所以zip文件名会在生成时由GeneratorService直接设置，这里只做模式匹配替换
    # 匹配格式：problem_xxx_testcase.zip，替换为问题ID对应的zip名
    # 由于sanitize_code只接收problem_id（规范化ID），zip名会在GeneratorService中设置
    code = re.sub(r'problem_[^_\s"]+_testcase\.zip', f'problem_{sanitize_filename(problem_id)}_testcase.zip', code)
    
    return code
