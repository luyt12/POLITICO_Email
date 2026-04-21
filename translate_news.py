"""
POLITICO EU News Translator
逐篇翻译：每篇独立保存到 translate/ 目录。
Primary: Kimi K2.5 (summarize + translate)
Fallback: Baidu AI Translation (translate only, on Kimi failure)
"""
import os
import sys
import glob
import logging
import requests
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

KIMI_API_KEY = os.getenv("kimi_API_KEY")
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2.5")
KIMI_API_URL = os.getenv(
    "KIMI_API_URL",
    "https://integrate.api.nvidia.com/v1/chat/completions"
)
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")

INPUT_DIR = "dailynews"
OUTPUT_DIR = "translate"

PROMPT = """你是一位专业的英语媒体编辑。请完成以下任务：

仔细阅读原文，提取最重要的信息并翻译为简体中文，遵循以下要求：
1. 输出 300-500 字符的中文摘要
2. 使用 Markdown 格式，文章标题用二级标题（##）
3. 标题下方注明原文链接
4. 准确性：忠实于原文，保留关键引语和数据
5. 流畅性：自然现代的中文，避免翻译腔
6. 简洁性：拆分长句，用词精准
7. 至少包含一句原文中的精彩引语

直接输出中文摘要，无需任何引导性语句。"""


def kimi_translate(content):
    """Primary: summarize + translate via Kimi LLM."""
    if not KIMI_API_KEY:
        logging.error("[KIMI] Missing kimi_API_KEY")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KIMI_API_KEY}"
    }
    payload = {
        "model": KIMI_MODEL,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user",   "content": content[:6000]}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    for attempt in range(5):
        try:
            logging.info(f"[KIMI] attempt {attempt + 1}/5...")
            resp = requests.post(
                KIMI_API_URL, headers=headers, json=payload, timeout=300
            )
            resp.raise_for_status()
            result = resp.json()
            choices = result.get("choices")
            if choices and choices[0]:
                text = choices[0]["message"]["content"]
                logging.info(f"[KIMI] OK ({len(text)} chars)")
                return text
            # Empty response
            logging.warning(f"[KIMI] Empty response body")
            if attempt < 4:
                time.sleep(30 * (2 ** attempt))
        except Exception as e:
            err_msg = str(e)
            # 401 = bad key, don't retry
            if "401" in err_msg or "403" in err_msg:
                logging.error(f"[KIMI] Auth error — abort: {err_msg}")
                break
            logging.warning(f"[KIMI] attempt {attempt+1} failed: {err_msg}")
            if attempt < 4:
                time.sleep(30 * (2 ** attempt))
    return None


def baidu_translate(text):
    """Fallback: translate via Baidu AI Translation (Bearer Token)."""
    if not BAIDU_API_KEY:
        logging.error("[BAIDU] Missing BAIDU_API_KEY")
        return None

    # Strip markdown headings for cleaner translation
    lines = text.split("\n")
    body_lines = [l for l in lines if not l.startswith("# ")]
    body = "\n".join(body_lines)[:2800]

    endpoint = "https://fanyi-api.baidu.com/ait/api/aiTextTranslate"
    for attempt in range(3):
        try:
            logging.info(f"[BAIDU] attempt {attempt+1}/3...")
            resp = requests.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {BAIDU_API_KEY}"
                },
                json={"q": body, "from": "en", "to": "zh"},
                timeout=30
            )
            data = resp.json()
            if data.get("error_code"):
                logging.error(f"[BAIDU] API error: {data['error_code']} — {data.get('error_msg','')}")
                if attempt < 2:
                    time.sleep(5)
                continue
            trans = (data.get("data") or {}).get("trans_result", "")
            if trans:
                logging.info(f"[BAIDU] OK ({len(trans)} chars)")
                return trans
            logging.warning(f"[BAIDU] No trans_result in response")
        except Exception as e:
            logging.warning(f"[BAIDU] attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(5)
    return None


def translate_article(filepath):
    """
    翻译单个 .md 文件（包含一篇或上下拼接的多篇文章）。
    逐##标题拆分，每篇独立翻译后拼接保存。
    """
    if not os.path.exists(filepath):
        logging.error(f"File not found: {filepath}")
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    outpath = os.path.join(OUTPUT_DIR, os.path.basename(filepath))

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    logging.info(f"Translating: {filepath} ({len(content)} chars)")

    # 解析出各篇文章
    articles = []
    import re
    parts = re.split(r"\n## ", "\n" + content)
    # parts[0] = 开头内容（无##前缀的），parts[1:] = 后续各篇
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        if i == 0:
            # 第一篇：已含##标题
            articles.append(part.strip())
        else:
            articles.append("## " + part.strip())

    logging.info(f"Found {len(articles)} article(s) to translate")

    translated = []
    for idx, article in enumerate(articles):
        # 提取标题
        title_m = re.search(r"^## (.+)", article)
        title = title_m.group(1) if title_m else f"Article {idx+1}"
        link_m = re.search(r"链接：(.+)", article)
        link = link_m.group(1) if link_m else ""
        logging.info(f"[{idx+1}/{len(articles)}] {title[:50]}")

        # 翻译
        result = kimi_translate(article)
        if result is None:
            logging.warning(f"[{idx+1}] Kimi failed — trying Baidu...")
            result = baidu_translate(article)
            if result is None:
                logging.error(f"[{idx+1}] All translators failed — skip")
                continue

        # 追加到输出
        translated.append(result)
        # 每篇之间休息一下避免限流
        if idx < len(articles) - 1:
            time.sleep(3)

    if not translated:
        logging.error("No articles translated")
        return None

    full_output = "\n\n---\n\n".join(translated)
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(full_output)
    logging.info(f"Saved: {outpath} ({len(full_output)} chars, {len(translated)} articles)")
    return full_output


if __name__ == "__main__":
    # 作为独立脚本运行时，翻译今日文件（按修改时间最新）
    md_files = sorted(
        glob.glob(os.path.join(INPUT_DIR, "*.md")),
        key=os.path.getmtime,
        reverse=True
    )
    if not md_files:
        logging.error("No .md files found in " + INPUT_DIR)
        sys.exit(1)

    latest = md_files[0]
    logging.info(f"Script mode: translating {latest}")
    ok = translate_article(latest)
    sys.exit(0 if ok else 1)
