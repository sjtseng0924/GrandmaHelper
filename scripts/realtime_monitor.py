#!/usr/bin/env python3
"""
實時監控腳本：即時顯示手機端的所有變動資訊
Real-time monitor script: Display all changes from mobile device instantly

功能特色 Features:
- 🔄 實時監控手機端所有變動
- 📱 支援全部資料，不限於好友資料
- 🎨 彩色 terminal 顯示
- ⚡ 即時響應變化
- 📊 顯示變化差異
- 🔍 支援資料過濾和搜尋

使用方法 Usage:
1. 確保 Android 設備已連接且 ADB 可用
2. 啟動 LineHelperApp 並開啟 Accessibility Service
3. 運行此腳本：python realtime_monitor.py
4. 操作手機，terminal 會即時顯示所有變化

命令列參數 Command line options:
--poll-interval: 輪詢間隔（毫秒，預設500）
--filter: 過濾關鍵字
--no-color: 停用彩色顯示
--verbose: 顯示詳細資訊
--save-json, -s: 將監控資料儲存成 JSON 檔案
--json-file, -j: 指定 JSON 檔案名稱（預設: monitor_log_YYYYMMDD_HHMMSS.json）
--save-all: 儲存所有資料（預設只儲存變動）

範例 Examples:
# 基本監控並儲存變動
python realtime_monitor.py --save-json

# 儲存所有資料到指定檔案
python realtime_monitor.py --save-json --save-all --json-file my_monitor.json

# 過濾特定關鍵字並儲存
python realtime_monitor.py --filter "好友" --save-json
"""

import requests
import json
import subprocess
import time
import sys
import argparse
from datetime import datetime
import os
import difflib
from pathlib import Path

# 顏色設定
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    
    @classmethod
    def disable(cls):
        cls.RESET = cls.BOLD = cls.RED = cls.GREEN = cls.YELLOW = ""
        cls.BLUE = cls.PURPLE = cls.CYAN = cls.WHITE = ""

# 配置
DEVICE_PORT = 8765
LOCAL_PORT = 8765
SERVER_URL = f"http://localhost:{LOCAL_PORT}"

class RealTimeMonitor:
    def __init__(self, poll_interval=500, filter_keyword=None, verbose=False, save_json=False, json_file=None, save_all=False):
        self.poll_interval = poll_interval / 1000.0  # 轉換為秒
        self.filter_keyword = filter_keyword
        self.verbose = verbose
        self.last_data = None
        self.last_timestamp = 0
        self.change_count = 0
        self.save_json = save_json
        self.save_all = save_all
        self.json_records = []
        
        # 設定 JSON 檔案路徑
        if json_file:
            self.json_file = Path(json_file)
        else:
            # 預設檔名包含日期時間
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.json_file = Path(f'monitor_log_{timestamp}.json')
        
    def setup_adb_forwarding(self):
        """設置 ADB 端口轉發"""
        try:
            # 檢查 ADB 設備連接
            result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
            if 'device' not in result.stdout:
                print(f"{Colors.RED}❌ 沒有檢測到 ADB 設備連接{Colors.RESET}")
                print("請確保：")
                print("1. Android 設備已連接並開啟 USB 調試")
                print("2. ADB 驅動已正確安裝")
                return False
            
            # 設置端口轉發
            subprocess.run(['adb', 'forward', f'tcp:{LOCAL_PORT}', f'tcp:{DEVICE_PORT}'], 
                          capture_output=True, text=True)
            print(f"{Colors.GREEN}✅ ADB 端口轉發已設置：localhost:{LOCAL_PORT} -> device:{DEVICE_PORT}{Colors.RESET}")
            return True
            
        except FileNotFoundError:
            print(f"{Colors.RED}❌ 找不到 ADB 命令{Colors.RESET}")
            print("請確保 Android SDK 已安裝且 ADB 在 PATH 中")
            return False
        except Exception as e:
            print(f"{Colors.RED}❌ 設置 ADB 端口轉發時出錯：{e}{Colors.RESET}")
            return False

    def test_connection(self):
        """測試連接"""
        try:
            response = requests.get(f"{SERVER_URL}/health", timeout=5)
            if response.status_code == 200 and response.text == "ok":
                print(f"{Colors.GREEN}✅ 服務器連接正常{Colors.RESET}")
                return True
            else:
                print(f"{Colors.RED}❌ 服務器連接失敗：{response.status_code} - {response.text}{Colors.RESET}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"{Colors.RED}❌ 無法連接到服務器：{e}{Colors.RESET}")
            print("請確保：")
            print("1. LineHelperApp 已在 Android 設備上運行")
            print("2. Accessibility Service 已開啟")
            print("3. 應用具有必要的權限")
            return False

    def get_current_data(self):
        """獲取當前數據"""
        try:
            response = requests.get(f"{SERVER_URL}/screen-info", timeout=3)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception:
            return None

    def format_timestamp(self, timestamp_ms):
        """格式化時間戳"""
        if timestamp_ms > 0:
            dt = datetime.fromtimestamp(timestamp_ms / 1000)
            return dt.strftime('%H:%M:%S.%f')[:-3]  # 顯示到毫秒
        return "未知時間"

    def clear_screen(self):
        """清空螢幕"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self):
        """打印標題"""
        print(f"{Colors.BOLD}{Colors.CYAN}")
        print("=" * 80)
        print("🔄 實時監控 - 手機端變動即時顯示")
        print("=" * 80)
        print(f"{Colors.RESET}")
        print(f"{Colors.YELLOW}監控間隔: {self.poll_interval * 1000:.0f}ms | 變化次數: {self.change_count}{Colors.RESET}")
        if self.filter_keyword:
            print(f"{Colors.PURPLE}🔍 過濾關鍵字: {self.filter_keyword}{Colors.RESET}")
        if self.save_json:
            print(f"{Colors.GREEN}💾 記錄到: {self.json_file}{Colors.RESET}")
            if self.save_all:
                print(f"{Colors.BLUE}📝 記錄模式: 所有資料{Colors.RESET}")
            else:
                print(f"{Colors.BLUE}📝 記錄模式: 僅變動{Colors.RESET}")
        print()

    def filter_content(self, content):
        """過濾內容"""
        if not self.filter_keyword:
            return content
        
        lines = content.split('\n')
        filtered_lines = []
        for line in lines:
            if self.filter_keyword.lower() in line.lower():
                # 高亮顯示匹配的關鍵字
                highlighted = line.replace(
                    self.filter_keyword,
                    f"{Colors.BOLD}{Colors.YELLOW}{self.filter_keyword}{Colors.RESET}"
                )
                filtered_lines.append(highlighted)
        
        return '\n'.join(filtered_lines) if filtered_lines else f"{Colors.RED}(沒有符合過濾條件的內容){Colors.RESET}"

    def show_diff(self, old_content, new_content):
        """顯示內容差異"""
        if not old_content or not new_content:
            return
        
        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')
        
        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile='舊資料', tofile='新資料',
            lineterm='', n=3
        ))
        
        if len(diff) > 2:  # 有實際差異
            print(f"{Colors.BOLD}{Colors.BLUE}📝 內容變化差異：{Colors.RESET}")
            print(f"{Colors.CYAN}─{Colors.RESET}" * 60)
            
            for line in diff[3:]:  # 跳過標題行
                if line.startswith('+'):
                    print(f"{Colors.GREEN}+ {line[1:]}{Colors.RESET}")
                elif line.startswith('-'):
                    print(f"{Colors.RED}- {line[1:]}{Colors.RESET}")
                elif line.startswith('@@'):
                    print(f"{Colors.YELLOW}{line}{Colors.RESET}")
            
            print(f"{Colors.CYAN}─{Colors.RESET}" * 60)
            print()

    def display_data(self, data, show_diff=True):
        """顯示數據"""
        if not data:
            print(f"{Colors.RED}❌ 無法獲取數據{Colors.RESET}")
            return
        
        # 提取資訊
        summary_text = data.get('summaryText', '')
        timestamp_ms = data.get('timestampMs', 0)
        
        # 清空螢幕並顯示標題
        self.clear_screen()
        self.print_header()
        
        # 顯示時間資訊
        current_time = self.format_timestamp(timestamp_ms)
        print(f"{Colors.BOLD}⏰ 資料時間: {Colors.GREEN}{current_time}{Colors.RESET}")
        
        if self.last_timestamp > 0:
            time_diff = timestamp_ms - self.last_timestamp
            print(f"{Colors.BOLD}⏱️  變化間隔: {Colors.CYAN}{time_diff}ms{Colors.RESET}")
        
        print()
        
        # 過濾和顯示內容
        filtered_content = self.filter_content(summary_text)
        
        print(f"{Colors.BOLD}{Colors.WHITE}📱 手機端資訊：{Colors.RESET}")
        print(f"{Colors.CYAN}─{Colors.RESET}" * 80)
        print(filtered_content)
        print(f"{Colors.CYAN}─{Colors.RESET}" * 80)
        print()
        
        # 顯示差異（如果有舊資料）
        if show_diff and self.last_data and self.verbose:
            self.show_diff(self.last_data.get('summaryText', ''), summary_text)
        
        # 顯示統計資訊
        line_count = len(summary_text.split('\n'))
        char_count = len(summary_text)
        print(f"{Colors.PURPLE}📊 資料統計: {line_count} 行, {char_count} 字元{Colors.RESET}")
        
        # 顯示操作提示
        print(f"\n{Colors.YELLOW}💡 按 Ctrl+C 停止監控{Colors.RESET}")

    def detect_changes(self, current_data):
        """檢測變化"""
        if not self.last_data:
            return True
        
        # 比較時間戳
        current_timestamp = current_data.get('timestampMs', 0)
        last_timestamp = self.last_data.get('timestampMs', 0)
        
        if current_timestamp != last_timestamp:
            return True
        
        # 比較內容
        current_content = current_data.get('summaryText', '')
        last_content = self.last_data.get('summaryText', '')
        
        return current_content != last_content
    
    def save_to_json(self, data, is_change=True):
        """將資料存成 JSON"""
        if not self.save_json:
            return
        
        # 準備記錄
        record = {
            'timestamp': datetime.now().isoformat(),
            'timestamp_ms': data.get('timestampMs', 0),
            'is_change': is_change,
            'change_count': self.change_count,
            'summary_text': data.get('summaryText', ''),
            'raw_data': data
        }
        
        # 如果有過濾條件，加入過濾關鍵字
        if self.filter_keyword:
            record['filter_keyword'] = self.filter_keyword
            record['filtered_content'] = self.filter_content(data.get('summaryText', ''))
        
        # 添加到記錄列表
        self.json_records.append(record)
        
        # 寫入檔案
        try:
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'monitor_session': {
                        'start_time': self.json_records[0]['timestamp'] if self.json_records else None,
                        'end_time': record['timestamp'],
                        'total_records': len(self.json_records),
                        'total_changes': self.change_count,
                        'poll_interval_ms': self.poll_interval * 1000,
                        'filter_keyword': self.filter_keyword,
                        'save_all': self.save_all
                    },
                    'records': self.json_records
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"{Colors.RED}❌ 儲存 JSON 時發生錯誤：{e}{Colors.RESET}")

    def run(self):
        """運行實時監控"""
        print(f"{Colors.BOLD}{Colors.GREEN}🚀 啟動實時監控系統{Colors.RESET}")
        print(f"監控間隔: {self.poll_interval * 1000:.0f}ms")
        if self.filter_keyword:
            print(f"過濾關鍵字: {self.filter_keyword}")
        print()
        
        # 設置 ADB
        if not self.setup_adb_forwarding():
            return False
        
        time.sleep(1)
        
        # 測試連接
        if not self.test_connection():
            return False
        
        print(f"{Colors.CYAN}🔄 開始監控... (按 Ctrl+C 停止){Colors.RESET}")
        time.sleep(2)
        
        try:
            while True:
                current_data = self.get_current_data()
                
                if current_data:
                    # 檢測是否有變化
                    has_change = self.detect_changes(current_data)
                    
                    if has_change:
                        self.change_count += 1
                        self.display_data(current_data)
                        
                        # 儲存變動到 JSON
                        self.save_to_json(current_data, is_change=True)
                        
                        # 更新最後一次的資料
                        self.last_timestamp = current_data.get('timestampMs', 0)
                        self.last_data = current_data
                    elif self.save_all:
                        # 如果選擇儲存所有資料（即使沒有變動）
                        self.save_to_json(current_data, is_change=False)
                    
                # 等待下次輪詢
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}🛑 用戶停止監控{Colors.RESET}")
            if self.save_json and self.json_records:
                print(f"{Colors.GREEN}💾 已儲存 {len(self.json_records)} 筆記錄到 {self.json_file}{Colors.RESET}")
            return True
        except Exception as e:
            print(f"\n{Colors.RED}❌ 監控過程中發生錯誤：{e}{Colors.RESET}")
            return False
        finally:
            # 清理端口轉發
            try:
                subprocess.run(['adb', 'forward', '--remove', f'tcp:{LOCAL_PORT}'], 
                              capture_output=True, text=True)
                print(f"{Colors.GREEN}🧹 已清理 ADB 端口轉發{Colors.RESET}")
            except:
                pass

def main():
    parser = argparse.ArgumentParser(description='實時監控手機端變動')
    parser.add_argument('--poll-interval', '-i', type=int, default=500,
                       help='轉詢間隔（毫秒，預設500）')
    parser.add_argument('--filter', '-f', type=str,
                       help='過濾關鍵字（只顯示包含此關鍵字的內容）')
    parser.add_argument('--no-color', action='store_true',
                       help='停用彩色顯示')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='顯示詳細資訊（包含差異比較）')
    parser.add_argument('--save-json', '-s', action='store_true',
                       help='將監控資料儲存成 JSON 檔案')
    parser.add_argument('--json-file', '-j', type=str,
                       help='指定 JSON 檔案名稱（預設: monitor_log_YYYYMMDD_HHMMSS.json）')
    parser.add_argument('--save-all', action='store_true',
                       help='儲存所有資料（預設只儲存變動）')
    
    args = parser.parse_args()
    
    # 停用顏色（如果要求）
    if args.no_color:
        Colors.disable()
    
    # 創建監控器
    monitor = RealTimeMonitor(
        poll_interval=args.poll_interval,
        filter_keyword=args.filter,
        verbose=args.verbose,
        save_json=args.save_json,
        json_file=args.json_file,
        save_all=args.save_all
    )
    
    # 執行監控
    success = monitor.run()
    
    if success:
        print(f"{Colors.GREEN}✅ 監控完成{Colors.RESET}")
    else:
        print(f"{Colors.RED}❌ 監控失敗{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()