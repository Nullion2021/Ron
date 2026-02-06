import os
import requests
import gzip
import re
import time
import random
from datetime import date, timedelta

# --- 配置区 ---
START_DATE = date(2026, 1, 1)  # 2026年1月1日
END_DATE = date(2026, 1, 31)   # 2026年1月31日
SAVE_DIR = "./data/raw_mjlog"
# 测试模式：每天只下 50 局。
# 如果想下载全量数据，请将下面这行改为: DOWNLOAD_LIMIT_PER_DAY = None
DOWNLOAD_LIMIT_PER_DAY = 50 
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://tenhou.net/"
}
# ----------------

def setup_dir():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"创建目录: {SAVE_DIR}")

def get_log_ids_for_date(target_date):
    # 构造文件名: scc2026010100.html.gz
    date_str = target_date.strftime("%Y%m%d")
    filename = f"scc{date_str}00.html.gz"
    
    # --- 修正点: 使用 dat 目录 ---
    url = f"https://tenhou.net/sc/raw/dat/{filename}"
    
    print(f"\n[列表] 正在获取 {target_date} 的数据: {url}")
    
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 404:
            print(f"[提示] {target_date} 的文件不存在 (可能日期不对或未归档)")
            return []
        resp.raise_for_status()
        
        content = gzip.decompress(resp.content).decode('utf-8')
        
        # 解析 Log ID
        pattern = r'log=([^"]+)'
        ids = re.findall(pattern, content)
        print(f"[列表] 找到 {len(ids)} 个牌谱")
        return ids
    except Exception as e:
        print(f"[错误] 获取列表失败: {e}")
        return []

def download_log(log_id):
    path = os.path.join(SAVE_DIR, f"{log_id}.mjlog")
    if os.path.exists(path):
        return # 已存在跳过
    
    url = f"https://tenhou.net/0/log/?{log_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            with open(path, "wb") as f:
                f.write(resp.content)
            print(f"  - 下载成功: {log_id}")
        else:
            print(f"  - 下载失败 {resp.status_code}: {log_id}")
    except Exception as e:
        print(f"  - 异常: {log_id} {e}")

def main():
    setup_dir()
    
    current_date = START_DATE
    while current_date <= END_DATE:
        log_ids = get_log_ids_for_date(current_date)
        
        count = 0
        for lid in log_ids:
            if DOWNLOAD_LIMIT_PER_DAY and count >= DOWNLOAD_LIMIT_PER_DAY:
                break
            
            download_log(lid)
            count += 1
            # 随机休眠
            time.sleep(random.uniform(1.0, 2.0))
            
        current_date += timedelta(days=1)
        time.sleep(1)

    print(f"\n任务完成！请检查目录: {os.path.abspath(SAVE_DIR)}")

if __name__ == "__main__":
    main()