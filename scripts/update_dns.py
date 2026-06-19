#!/usr/bin/env python3
"""
读取 CloudflareST 测速结果，更新阿里云 DNS A 记录。
用于 cf-test.chenxiuniverse.top 优选IP实验。
"""
import csv
import json
import os
import sys
import importlib
import time

from aliyunsdkcore.client import AcsClient

# ============================================================
# 配置 — 首次运行前确认以下内容
# ============================================================
DOMAIN = "chenxiuniverse.top"
TOP_N = 3  # 保留前 N 个最优 IP

# 阿里云 DNS 上 cf-test 的 3 条 A 记录的 RecordId
# 在阿里云DNS控制台 → chenxiuniverse.top → 解析设置 → 点记录 → URL中的record-id
RECORD_IDS = [
    "2067855433872104448",  # cf-test A 记录 #1
    "2067855435608468480",  # cf-test A 记录 #2
    "2067855437453883392",  # cf-test A 记录 #3
]
# ============================================================

def get_top_ips(csv_path="result.csv", top_n=TOP_N):
    """从 CloudflareST 输出的 CSV 中提取 Top N IP"""
    ips = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ip = row.get("IP 地址", "").strip()
                delay = row.get("平均延迟", "").strip()
                speed = row.get("下载速度 (MB/s)", "").strip()
                if ip and delay:
                    ips.append({
                        "ip": ip,
                        "delay": float(delay),
                        "speed": float(speed) if speed else 0
                    })
        print(f"📊 解析到 {len(ips)} 个有效 IP")
    except FileNotFoundError:
        print(f"❌ {csv_path} 未找到！")
        sys.exit(1)
    return ips[:top_n]


def update_record(client, record_id, rr, ip, ttl=600):
    """更新单条 DNS A 记录"""
    mod = importlib.import_module(
        'aliyunsdkalidns.request.v20150109.UpdateDomainRecordRequest'
    )
    req = mod.UpdateDomainRecordRequest()
    req.set_RecordId(record_id)
    req.set_RR(rr)
    req.set_Type("A")
    req.set_Value(ip)
    req.set_TTL(ttl)

    try:
        client.do_action_with_exception(req)
        print(f"  ✅ {rr}.{DOMAIN} → {ip}")
        return True
    except Exception as e:
        print(f"  ❌ {rr}.{DOMAIN} → {ip}: {e}")
        return False


def main():
    # 读取测速结果
    top_ips = get_top_ips("result.csv")
    if not top_ips:
        print("❌ 未找到有效 IP")
        sys.exit(1)

    # 打印 TOP 5
    all_ips = get_top_ips("result.csv", top_n=5)
    print(f"\n{'='*50}")
    print(f"🏆 优选 IP TOP {len(all_ips)}")
    for i, item in enumerate(all_ips):
        print(f"  #{i+1}: {item['ip']:20s} 延迟={item['delay']:6.1f}ms  速度={item['speed']:6.1f}MB/s")
    print(f"{'='*50}\n")

    # 连接阿里云
    client = AcsClient(
        os.environ["ALI_KEY_ID"],
        os.environ["ALI_KEY_SECRET"],
        "cn-hangzhou",
    )

    # 更新 DNS
    print("🔄 更新 DNS...")
    success = 0
    for i in range(len(RECORD_IDS)):
        if i < len(top_ips):
            if update_record(client, RECORD_IDS[i], "cf-test", top_ips[i]["ip"]):
                success += 1
        else:
            # 多余记录设为第一个最优 IP（保持一致）
            if update_record(client, RECORD_IDS[i], "cf-test", top_ips[0]["ip"]):
                success += 1

    print(f"\n✅ 完成: {success}/{len(RECORD_IDS)} 条记录已更新")
    print(f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S UTC')}")


if __name__ == "__main__":
    main()
