"""
POLITICO EU RSS Parser
抓取 https://www.politico.eu/feed/ 并按日期保存为 Markdown。
支持 backfill 模式（忽略 sent 状态）用于补发旧文章。
"""
import feedparser
import html2text
import os
import json
from datetime import datetime, timezone, timedelta
import pytz

RSS_URL = "https://www.politico.eu/feed/"
OUTPUT_DIR = "dailynews"
PROCESSED_FILE = "processed_urls.json"
MAX_DAILY = 10
TZ_EU = pytz.timezone("Europe/Brussels")


def load_processed():
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_processed(data):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_rss(force_backfill=False):
    """
    抓取 EU Politico RSS。
    force_backfill=True: 忽略 sent 状态，抓取最近 N 天的文章（用于补发）。
    正常模式：只抓今天 + 未发送的文章。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    processed = load_processed()

    print(f"正在抓取: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("警告: RSS 条目为空")
        return []

    now_eu = datetime.now(TZ_EU)
    today_str = now_eu.strftime("%Y-%m-%d")
    today_file = os.path.join(OUTPUT_DIR, today_str + ".md")

    if not force_backfill:
        # 正常模式：只抓今天 + 未处理
        candidates = []
        for entry in feed.entries:
            link = entry.get("link", "")
            title = entry.get("title", "无标题")
            if not link or link in processed:
                continue

            pub_dt = None
            try:
                pub_struct = entry.get("published_parsed")
                if pub_struct:
                    pub_dt = datetime(*pub_struct[:6], tzinfo=timezone.utc)
            except Exception:
                pass

            if pub_dt:
                eu_tz = pytz.timezone("Europe/Brussels")
                eu_dt = pub_dt.astimezone(eu_tz)
                if eu_dt.strftime("%Y-%m-%d") != today_str:
                    continue
            else:
                continue

            candidates.append(entry)

        print(f"今日（欧洲时间 {today_str}）新文章: {len(candidates)} 篇")
        if not candidates:
            print("今日无新文章，跳过写入")
            return []

        selected = candidates[:MAX_DAILY]
    else:
        # backfill 模式：忽略 sent，抓最近 N 天的文章
        backfill_days = int(os.getenv("BACKFILL_DAYS", "4"))
        print(f"Backfill 模式: 最近 {backfill_days} 天")
        cutoff = now_eu - timedelta(days=backfill_days)
        candidates = []
        for entry in feed.entries:
            link = entry.get("link", "")
            if not link:
                continue

            pub_dt = None
            try:
                pub_struct = entry.get("published_parsed")
                if pub_struct:
                    pub_dt = datetime(*pub_struct[:6], tzinfo=timezone.utc)
            except Exception:
                pass

            if pub_dt:
                eu_tz = pytz.timezone("Europe/Brussels")
                eu_dt = pub_dt.astimezone(eu_tz)
                if eu_dt < cutoff:
                    continue
            candidates.append(entry)

        print(f"Backfill 候选: {len(candidates)} 篇")
        # 跳过已完整发送过的
        selected = []
        for entry in candidates:
            link = entry.get("link", "")
            if link in processed and processed[link].get("sent"):
                continue
            selected.append(entry)
        selected = selected[:MAX_DAILY]

    print(f"选取 {len(selected)} 篇")

    html_converter = html2text.HTML2Text()
    html_converter.body_width = 0

    saved = []
    for entry in selected:
        title = entry.get("title", "无标题")
        link = entry.get("link", "")
        content_html = ""
        if hasattr(entry, "content") and entry.content:
            content_html = entry.content[0].get("value", "")
        if not content_html and hasattr(entry, "summary"):
            content_html = entry.summary
        content_md = html_converter.handle(content_html).strip() if content_html else "（无正文）"

        item = f"## {title}\n\n链接：{link}\n\n{content_md}\n\n---\n\n"
        mode = "a" if os.path.exists(today_file) else "w"
        with open(today_file, mode, encoding="utf-8") as f:
            f.write(item)

        pub_str = today_str
        if pub_dt:
            try:
                eu_tz = pytz.timezone("Europe/Brussels")
                pub_str = pub_dt.astimezone(eu_tz).strftime("%Y-%m-%d")
            except Exception:
                pass

        processed[link] = {"title": title, "sent": False, "date": pub_str}
        saved.append(link)
        print(f"  已保存: {title[:60]}")

    save_processed(processed)
    print(f"本次新增 {len(saved)} 篇，文件: {today_file}")
    return saved


def mark_sent(urls):
    processed = load_processed()
    for url in urls:
        if url in processed:
            processed[url]["sent"] = True
    save_processed(processed)


if __name__ == "__main__":
    mode = os.getenv("MODE", "normal")
    force = (mode == "backfill")
    saved = fetch_rss(force_backfill=force)
    print(f"\n完成: 抓取 {len(saved)} 篇新文章")
