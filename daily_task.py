"""
POLITICO EU Daily Task
1. Fetch today's articles from RSS (deduped via processed_urls.json)
2. Translate via Kimi (with Baidu fallback)
3. Send email
4. Mark URLs as sent
"""
import os
import sys
import glob
import json

# Step 1: 抓取 RSS
print("Step 1: 抓取 RSS...")
import rss_parser
saved = rss_parser.fetch_rss()
if not saved:
    print("今日无新文章，结束")
    sys.exit(0)

# Step 2: 翻译
print("Step 2: 翻译文章...")
today_file = None
md_files = glob.glob(os.path.join("dailynews", "*.md"))
if md_files:
    today_file = sorted(md_files)[-1]
    print(f"翻译文件: {today_file}")

import translate_news
if today_file:
    result = translate_news.translate_article(today_file)
    if not result:
        print("翻译失败，退出")
        sys.exit(1)
else:
    print("无今日文件，跳过翻译")
    sys.exit(1)

# Step 3: 发送邮件
print("Step 3: 发送邮件...")
import send_email
translate_file = os.path.join("translate", os.path.basename(today_file))
if os.path.exists(translate_file):
    send_email.main(translate_file)
else:
    print("无翻译文件，跳过发送")

# Step 4: 标记已发送
print("Step 4: 标记已发送...")
rss_parser.mark_sent(saved)
print("完成!")
