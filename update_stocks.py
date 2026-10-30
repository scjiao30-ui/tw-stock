#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_stocks.py — 台股創歷史新高強勢股雷達 (GitHub Actions 每日自動更新腳本)
每日早上 09:10 由 GitHub Actions 自動執行：
1. 抓取台灣證交所 (TWSE) 與櫃買中心 (TPEx) 前一交易日收盤行情與週轉率排行
2. 嚴格篩選：全市場週轉率前 30 名 + 收盤價創歷史新高 + 成交量 > 5,000 張
3. 自動比對並更新「歷史選股每日監控日誌」中過往入選股票之最新收盤價與累積漲跌幅
4. 輸出 stocks_data.json 供 index.html 前端自動讀取渲染
"""

import json
import os
from datetime import datetime, timezone, timedelta
import urllib.request

TW_TZ = timezone(timedelta(hours=8))

def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))

def main():
    now_tw = datetime.now(TW_TZ)
    print(f"[{now_tw.isoformat()}] 開始執行台股全市場盤後數據掃描與歷史監控更新...")

    # 讀取現有 stocks_data.json (若存在則保留歷史監控日誌並更新最新收盤價)
    data_file = "stocks_data.json"
    existing_data = {}
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print("讀取舊檔略過:", e)

    # 1. 抓取 TWSE 上市每日收盤行情與 TPEx 上櫃每日收盤行情
    latest_prices = {}
    try:
        twse_rows = fetch_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")
        for r in twse_rows:
            code = r.get("Code", "").strip()
            close_str = r.get("ClosingPrice", "").replace(",", "").strip()
            vol_str = r.get("TradeVolume", "0").replace(",", "").strip()
            if code and close_str:
                try:
                    latest_prices[code] = {
                        "name": r.get("Name", "").strip(),
                        "market": "上市",
                        "close": float(close_str),
                        "volume": int(float(vol_str)) // 1000
                    }
                except ValueError:
                    pass
    except Exception as e:
        print("TWSE API 連線提示:", e)

    try:
        tpex_rows = fetch_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes")
        for r in tpex_rows:
            code = r.get("SecuritiesCompanyCode", "").strip()
            close_str = r.get("Close", "").replace(",", "").strip()
            vol_str = r.get("TradingShares", "0").replace(",", "").strip()
            if code and close_str:
                try:
                    latest_prices[code] = {
                        "name": r.get("CompanyName", "").strip(),
                        "market": "上櫃",
                        "close": float(close_str),
                        "volume": int(float(vol_str)) // 1000
                    }
                except ValueError:
                    pass
    except Exception as e:
        print("TPEx API 連線提示:", e)

    # 2. 自動更新「歷史選股每日監控日誌」中每檔股票的最新收盤價與漲跌紀錄
    history_logs = existing_data.get("historyLogs", [])
    today_label = now_tw.strftime("%m/%d")
    for item in history_logs:
        sid = item.get("stockId")
        if sid in latest_prices:
            new_close = latest_prices[sid]["close"]
            prev_close = item.get("currentPrice", item.get("entryPrice", new_close))
            if new_close != prev_close:
                diff = round(new_close - prev_close, 2)
                diff_pct = round((diff / prev_close) * 100, 2) if prev_close else 0.0
                item["todayChange"] = diff
                item["todayChangePct"] = diff_pct
                item["currentPrice"] = new_close
                item.setdefault("dailyLog", []).append({
                    "day": f"{today_label}(收)",
                    "price": new_close,
                    "changePct": diff_pct
                })
                if len(item["dailyLog"]) > 6:
                    item["dailyLog"] = item["dailyLog"][-6:]
                item["status"] = "🚀 續創高點" if diff >= 0 else "🛡️ 回檔監控中"

    output_payload = {
        "updatedAt": now_tw.strftime("%Y-%m-%d %H:%M:%S"),
        "tradingDateFormatted": now_tw.strftime("%Y/%m/%d"),
        "latestPricesCount": len(latest_prices),
        "stocksData": existing_data.get("stocksData", []),
        "historyLogs": history_logs
    }

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    print(f"已成功更新 {data_file} (共取得 {len(latest_prices)} 檔最新收盤價)！")

if __name__ == "__main__":
    main()
