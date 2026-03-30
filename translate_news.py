import os
import sys
import glob
import logging
import requests
import time

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 配置（直接从环境变量读取）---
KIMI_API_KEY = os.getenv("kimi_API_KEY")
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2.5")
KIMI_API_URL = os.getenv("KIMI_API_URL", "https://integrate.api.nvidia.com/v1/chat/completions")

INPUT_DIR = "dailynews"
OUTPUT_DIR = "translate"

# --- 翻译提示词 ---
TRANSLATION_PROMPT = """你是一位专业的翻译者，擅长将 POLITICO 新闻，翻译为简体中文，请对我给出的内容进行翻译。请遵循以下要求：

# 翻译格式
1. 使用Markdown格式输出
2. 将所有英文内容进行翻译，包括：标题、正文等
3. 输出时，完整保留原始内容中，所有无需翻译的内容，不要遗漏
4. 每篇翻译报道的标题，使用Markdown二级标题(##)
5. 在每篇翻译报道下，注明原文的链接网址，不要改动

# 翻译风格与要求
1. 准确性：忠实于原文意义，不歪曲、不遗漏关键信息
2. 流畅性：译文清晰易懂，逻辑连贯，符合现代简体中文的表达习惯
3. 简洁与优雅：
* **主动拆分长句**：当英文原句较长时，应主动将其拆分为多个更短、更简洁的中文句子。
* **优化语序**：采用地道的中文语序和表达方式。
* **精炼用词**：选择精准、简洁的词汇。
* **避免"翻译腔"**：特别注意避免直接套用英文的句式结构

# 注意事项
1. 直接输出，不要加入任何与原始内容无关的回应性语句"""

def translate_with_kimi(content):
    """使用 Kimi K2.5 API (NVIDIA endpoint) 翻译内容"""
    if not KIMI_API_KEY:
        logging.error("未设置 kimi_API_KEY 环境变量")
        sys.exit(1)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KIMI_API_KEY}"
    }
    
    data = {
        "model": KIMI_MODEL,
        "messages": [
            {"role": "system", "content": TRANSLATION_PROMPT},
            {"role": "user", "content": content}
        ],
        "temperature": 0.7,
        "max_tokens": 16000
    }
    
    max_retries = 5
    
    for attempt in range(max_retries):
        try:
            logging.info(f"发送翻译请求 (尝试 {attempt + 1}/{max_retries})...")
            response = requests.post(
                KIMI_API_URL,
                headers=headers,
                json=data,
                timeout=300
            )
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                logging.error(f"API 响应异常: {result}")
                if attempt < max_retries - 1:
                    wait = 30 * (2 ** attempt)
                    logging.info(f"等待 {wait} 秒后重试...")
                    time.sleep(wait)
                    
        except requests.exceptions.Timeout:
            logging.error(f"API 请求超时 (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                wait = 30 * (2 ** attempt)
                logging.info(f"等待 {wait} 秒后重试...")
                time.sleep(wait)
                
        except requests.exceptions.RequestException as e:
            logging.error(f"API 请求失败: {e}")
            if attempt < max_retries - 1:
                wait = 30 * (2 ** attempt)
                logging.info(f"等待 {wait} 秒后重试...")
                time.sleep(wait)
                
        except Exception as e:
            logging.error(f"未知错误: {e}")
            if attempt < max_retries - 1:
                time.sleep(30)
                
    return None

def translate_file(input_file_path):
    """翻译指定的 .md 文件并保存结果"""
    if not os.path.exists(input_file_path):
        logging.error(f"文件不存在: {input_file_path}")
        return False
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 从输入文件名获取输出文件名
    filename = os.path.basename(input_file_path)
    output_file_path = os.path.join(OUTPUT_DIR, filename)
    
    logging.info(f"开始翻译文件: {input_file_path}")
    
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logging.info(f"内容长度: {len(content)} 字符")
        translated_content = translate_with_kimi(content)
        
        if translated_content:
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            logging.info(f"翻译完成，已保存到: {output_file_path}")
            return True
        else:
            logging.error(f"翻译失败: {input_file_path}")
            return False
    except Exception as e:
        logging.error(f"处理文件时发生错误: {e}")
        return False

def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 支持完整路径，如 "dailynews/20260330.md" 或 "20260330.md"
        input_file = sys.argv[1]
        if not input_file.endswith('.md'):
            input_file += '.md'
        
        # 如果包含路径分隔符，直接使用
        if os.path.sep in input_file or '/' in input_file or '\\' in input_file:
            input_file_path = input_file
        else:
            input_file_path = os.path.join(INPUT_DIR, input_file)
    else:
        # 否则找最新的文件
        md_files = glob.glob(os.path.join(INPUT_DIR, "*.md"))
        if not md_files:
            logging.error("找不到任何 .md 文件")
            sys.exit(1)
        input_file_path = max(md_files, key=os.path.getmtime)
    
    if not os.path.exists(input_file_path):
        logging.error(f"找不到要翻译的文件: {input_file_path}")
        sys.exit(1)
    
    success = translate_file(input_file_path)
    
    if success:
        logging.info("翻译任务完成")
    else:
        logging.error("翻译任务失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
