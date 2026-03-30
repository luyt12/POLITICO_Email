import os
import logging
import pytz
from datetime import datetime
from flask import Flask, Response
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import requests

# 导入项目中的其他模块
import rss_parser
import translate_news
import send_email

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

# 创建 Flask 应用
app = Flask(__name__)

# 定义常量
DAILYNEWS_DIR = "dailynews"
TRANSLATE_DIR = "translate"
TIMEZONE_EST = pytz.timezone('America/New_York')

# 获取当天日期字符串（美国东部时间）
def get_today_date_str():
    """获取当前美国东部时间的日期字符串，格式为 YYYYMMDD"""
    now = datetime.now(TIMEZONE_EST)
    return now.strftime('%Y%m%d')

# 执行每日新闻流程：抓取 → 翻译 → 发邮件
def process_daily_news():
    """
    执行每日新闻流程：
    1. 调用 rss_parser.py 抓取新闻
    2. 调用 translate_news.py 翻译新闻
    3. 调用 send_email.py 发送邮件
    """
    today_date = get_today_date_str()
    logging.info(f"开始执行每日新闻流程，当前日期: {today_date}")
    
    # 步骤 1: 抓取新闻
    logging.info("步骤 1: 执行 rss_parser.py 抓取新闻")
    try:
        rss_parser.main()
    except Exception as e:
        logging.error(f"执行 rss_parser.py 失败: {e}")
        return
    
    # 步骤 2: 检查并翻译当天的新闻
    dailynews_file = os.path.join(DAILYNEWS_DIR, f"{today_date}.md")
    if os.path.exists(dailynews_file):
        logging.info(f"步骤 2: 发现当天的 dailynews 文件: {dailynews_file}")
        try:
            translate_news.translate_file(dailynews_file)
        except Exception as e:
            logging.error(f"执行 translate_news.py 处理 {dailynews_file} 失败: {e}")
            return
    else:
        logging.warning(f"步骤 2: 未找到当天的 dailynews 文件: {dailynews_file}")
        return
    
    # 步骤 3: 发送邮件
    translate_file = os.path.join(TRANSLATE_DIR, f"{today_date}.md")
    if os.path.exists(translate_file):
        logging.info(f"步骤 3: 发现当天的 translate 文件: {translate_file}")
        try:
            success = send_email.send_daily_email(today_date)
            if success:
                logging.info(f"✅ 每日新闻邮件发送成功 ({today_date})")
            else:
                logging.error(f"❌ 每日新闻邮件发送失败 ({today_date})")
        except Exception as e:
            logging.error(f"发送邮件失败: {e}")
    else:
        logging.warning(f"步骤 3: 未找到当天的 translate 文件: {translate_file}")

# Flask 路由
@app.route('/')
def index():
    """提供简单的状态页面"""
    today_date = get_today_date_str()
    return f"""
    <html>
        <head><title>POLITICO 每日新闻</title></head>
        <body>
            <h1>POLITICO 每日新闻邮件服务</h1>
            <p>服务运行中...</p>
            <p>当前日期 (EST): {today_date}</p>
            <p>每日 22:00 (美国东部时间) 自动抓取、翻译并发送邮件</p>
        </body>
    </html>
    """

# 自我 ping 函数（保持服务活跃）
def ping_self():
    """ping 自己以保持服务活跃"""
    try:
        host = os.environ.get('HOST', 'localhost')
        port = os.environ.get('PORT', '5000')
        url = f"http://{host}:{port}/"
        
        logging.info(f"正在 ping: {url}")
        response = requests.get(url, timeout=10)
        logging.info(f"Ping 结果: {response.status_code}")
    except Exception as e:
        logging.error(f"Ping 失败: {e}")

# 初始化调度器
def init_scheduler():
    """初始化定时任务调度器"""
    scheduler = BackgroundScheduler()

    # 添加美国东部时间 22:00 的每日新闻任务
    scheduler.add_job(
        process_daily_news,
        trigger=CronTrigger(hour=22, minute=0, timezone=TIMEZONE_EST),
        id='daily_news_email',
        name='Daily News Email at 22:00 EST',
        replace_existing=True
    )

    # 添加每 5 分钟 ping 自己的任务
    scheduler.add_job(
        ping_self,
        trigger=IntervalTrigger(minutes=5),
        id='self_ping',
        name='Ping self every 5 minutes',
        replace_existing=True
    )

    scheduler.start()
    logging.info("调度器已启动")

# 启动时可选执行一次新闻流程（取消下面注释即可启用）
# process_daily_news()

# 初始化调度器
init_scheduler()

# 本地开发时运行
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
