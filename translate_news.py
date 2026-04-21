"""
POLITICO EU News Translator
逐篇翻译：每篇独立保存到 translate/ 目录。
使用百度翻译 API（大模型文本翻译），API Key 鉴权。
"""
import os
import sys
import glob
import logging
import requests
import time
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

# 百度翻译 API 配置（大模型文本翻译）
BAIDU_APPID = os.getenv("BAIDU_APPID", "")
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")
BAIDU_API_URL = "https://fanyi-api.baidu.com/ait/api/aiTextTranslate"

INPUT_DIR = "dailynews"
OUTPUT_DIR = "translate"

# 百度错误码
BAIDU_AUTH_ERRORS = {"52001", "52002", "52003"}
BAIDU_QUOTA_ERROR = "54000"
BAIDU_RATE_LIMIT = "54003"


def baidu_translate(text):
    """
    百度翻译 API（大模型文本翻译）。
    返回: (translated_text, should_abort)
    """
    if not BAIDU_API_KEY:
        logging.error("[BAIDU] BAIDU_API_KEY 未设置")
        return None, True
    if not BAIDU_APPID:
        logging.error("[BAIDU] BAIDU_APPID 未设置")
        return None, True

    # 去掉 markdown 标题，只翻译正文
    lines = text.split("\n")
    body_lines = [l for l in lines if not l.startswith("# ")]
    body = "\n".join(body_lines)[:2800]

    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            resp = requests.post(
                BAIDU_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {BAIDU_API_KEY}"
                },
                json={
                    "appid": BAIDU_APPID,
                    "q": body,
                    "from": "en",
                    "to": "zh"
                },
                timeout=60
            )
            data = resp.json()

            # 检查错误
            error_code = str(data.get("error_code", ""))
            if error_code:
                error_msg = data.get("error_msg", "未知错误")

                if error_code in BAIDU_AUTH_ERRORS:
                    logging.error(f"[BAIDU] 认证失败 ({error_code}): {error_msg}")
                    return None, True

                if error_code == BAIDU_QUOTA_ERROR:
                    logging.error(f"[BAIDU] 余额不足 ({error_code}): {error_msg}")
                    return None, True

                if error_code == BAIDU_RATE_LIMIT:
                    if attempt == 0:
                        logging.warning("[BAIDU] 速率限制，等待1秒后重试...")
                        time.sleep(1)
                        continue
                    return None, False

                logging.warning(f"[BAIDU] API 错误 ({error_code}): {error_msg}")
                return None, False

            # 成功响应：直接从 trans_result 提取
            trans_result = data.get("trans_result", [])
            if trans_result and isinstance(trans_result, list):
                # 合并所有翻译片段
                translated = "\n".join([item.get("dst", "") for item in trans_result if isinstance(item, dict)])
                if translated:
                    logging.info(f"[BAIDU] 翻译成功 ({len(translated)} 字符)")
                    return translated, False

            logging.warning("[BAIDU] 响应中无翻译结果")
            return None, False

        except requests.exceptions.Timeout:
            logging.warning(f"[BAIDU] 请求超时 (attempt {attempt+1}/{max_attempts})")
            if attempt < max_attempts - 1:
                time.sleep(2)
                continue
            return None, False

        except requests.exceptions.ConnectionError as e:
            logging.warning(f"[BAIDU] 网络错误: {e}")
            if attempt < max_attempts - 1:
                time.sleep(2)
                continue
            return None, False

        except Exception as e:
            logging.error(f"[BAIDU] 未知错误: {e}")
            return None, False

    return None, False


def translate_article(filepath):
    """
    翻译单个 .md 文件。
    """
    if not os.path.exists(filepath):
        logging.error(f"文件不存在: {filepath}")
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    outpath = os.path.join(OUTPUT_DIR, os.path.basename(filepath))

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    logging.info(f"翻译文件: {filepath} ({len(content)} 字符)")

    import re
    parts = re.split(r"\n## ", "\n" + content)
    articles = []
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        if i == 0:
            articles.append(part.strip())
        else:
            articles.append("## " + part.strip())

    logging.info(f"发现 {len(articles)} 篇文章")

    translated = []
    failed_count = 0

    for idx, article in enumerate(articles):
        title_m = re.search(r"^## (.+)", article)
        title = title_m.group(1) if title_m else f"文章 {idx+1}"
        logging.info(f"[{idx+1}/{len(articles)}] {title[:50]}")

        result, should_abort = baidu_translate(article)

        if should_abort:
            logging.error("[BAIDU] 遇到关键错误，中止翻译任务")
            break

        if result is None:
            failed_count += 1
            logging.warning(f"[{idx+1}] 翻译失败，跳过")
            if failed_count >= 3:
                logging.error("连续失败 3 次，中止任务")
                break
            continue
        else:
            failed_count = 0
            translated.append(result)

        if idx < len(articles) - 1:
            time.sleep(1)

    if not translated:
        logging.error("没有文章翻译成功")
        return None

    full_output = "\n\n---\n\n".join(translated)
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(full_output)
    logging.info(f"已保存: {outpath} ({len(full_output)} 字符, {len(translated)} 篇)")
    return full_output


if __name__ == "__main__":
    md_files = sorted(
        glob.glob(os.path.join(INPUT_DIR, "*.md")),
        key=os.path.getmtime,
        reverse=True
    )
    if not md_files:
        logging.error(f"在 {INPUT_DIR} 中未找到 .md 文件")
        sys.exit(1)

    latest = md_files[0]
    logging.info(f"脚本模式: 翻译 {latest}")
    ok = translate_article(latest)
    sys.exit(0 if ok else 1)
