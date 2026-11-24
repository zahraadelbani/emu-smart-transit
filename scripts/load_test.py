"""Bounded real HTTP load test. Never target a server without authorization."""
import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8000/api/v1/buses/live/')
parser.add_argument('--requests', type=int, default=100)
parser.add_argument('--concurrency', type=int, default=10)
args = parser.parse_args()

def request(_):
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(args.url, timeout=15) as response:
            response.read()
            code = response.status
    except Exception as exc:
        code = str(type(exc).__name__)
    return (time.perf_counter() - start) * 1000, code

start = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
    results = list(pool.map(request, range(args.requests)))
latencies = sorted(r[0] for r in results)
print(json.dumps({'requests':len(results),'concurrency':args.concurrency,'success':sum(r[1]==200 for r in results),'elapsed_seconds':round(time.perf_counter()-start,2),'median_ms':round(statistics.median(latencies),2),'p95_ms':round(latencies[min(len(latencies)-1,int(len(latencies)*.95))],2)},indent=2))
