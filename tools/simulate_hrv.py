#!/usr/bin/env python3
"""
工具：向本地运行的 Flask 应用 POST 一个模拟 HRV 值到 `/api/simulate-hrv`，或直接写入文件（如果无法连接服务）。
用法：
    python tools/simulate_hrv.py 32.5
    python tools/simulate_hrv.py --host http://localhost:5001 18.2

如果指定了 host，会调用 HTTP 端点；否则直接写文件 `generated_audio/latest_hrv.txt`。
"""
import argparse
import os
import sys
import json
from urllib import request, error

def write_file(hrv):
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'generated_audio', 'latest_hrv.txt')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"{float(hrv):.4f}")
    print(f"Wrote HRV {hrv} to {path}")


def post_host(host, hrv):
    url = host.rstrip('/') + '/api/simulate-hrv'
    data = json.dumps({'hrv': float(hrv)}).encode('utf-8')
    req = request.Request(url, data=data, headers={'Content-Type':'application/json'})
    try:
        with request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode('utf-8')
            print('Response:', body)
    except error.URLError as e:
        print('Failed to POST to host:', e)
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('hrv', help='HRV（ms），例如 32.5')
    parser.add_argument('--host', help='可选：Flask 服务地址，例如 http://localhost:5001')
    args = parser.parse_args()

    if args.host:
        return post_host(args.host, args.hrv)
    else:
        write_file(args.hrv)
        return 0

if __name__ == '__main__':
    sys.exit(main())
