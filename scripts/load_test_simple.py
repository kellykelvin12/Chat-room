#!/usr/bin/env python3
"""
Simple load test script for the chat app.

Usage examples (PowerShell):
  # install dependencies
  pip install requests

  # simple test against relationship message endpoint (requires valid user)
  python scripts\load_test_simple.py --base http://127.0.0.1:5000 --login-user testuser --login-pass secret \
      --endpoint /api/send_relationship_message --relationship-id e74953ce-665e-4560-a739-422bad037e1d \
      --concurrency 10 --requests 200

This will log in, then perform concurrent POSTs and print latency and success stats.
"""
import argparse
import time
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except Exception:
    print('Please install requests: pip install requests')
    raise


def do_login(session, base, username, password):
    login_url = base.rstrip('/') + '/login'
    # The app's login expects form fields 'username' and 'password'
    r = session.post(login_url, data={'username': username, 'password': password}, allow_redirects=False)
    return r.status_code in (302, 200)


def send_message(session, url, data, files=None):
    start = time.perf_counter()
    try:
        r = session.post(url, data=data, files=files, timeout=30)
        elapsed = time.perf_counter() - start
        return (r.status_code, r.text, elapsed)
    except Exception as e:
        elapsed = time.perf_counter() - start
        return ('ERR', str(e), elapsed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True, help='Base URL, e.g. http://127.0.0.1:5000')
    parser.add_argument('--endpoint', required=True, help='Endpoint path, e.g. /api/send_relationship_message')
    parser.add_argument('--login-user', help='Username to login with')
    parser.add_argument('--login-pass', help='Password to login with')
    parser.add_argument('--concurrency', type=int, default=5)
    parser.add_argument('--requests', type=int, default=100)
    parser.add_argument('--relationship-id', help='Relationship ID when using relationship endpoint')
    parser.add_argument('--use-relationship', action='store_true', help='Send relationship message payload')
    parser.add_argument('--file', help='Optional file to upload as image (path)')
    args = parser.parse_args()

    base = args.base.rstrip('/')
    url = base + args.endpoint

    session = requests.Session()

    if args.login_user:
        ok = do_login(session, base, args.login_user, args.login_pass or '')
        if not ok:
            print('Login failed with provided credentials')
            return
        print('Login OK')

    total = args.requests
    concurrency = args.concurrency

    print(f'Running {total} requests with concurrency={concurrency} against {url}')

    latencies = []
    successes = 0
    errors = 0

    def task(i):
        payload = None
        files = None
        if args.use_relationship:
            payload = {
                'relationship_id': args.relationship_id or '',
                'content': f'loadtest message {i} {random.randint(1,99999)}',
                'identity_revealed': 'false',
                'voice_type': 'normal'
            }
        else:
            # generic message payload for /api/send_message
            payload = {
                'topic_id': args.relationship_id or '',
                'content': f'loadtest message {i} {random.randint(1,99999)}',
                'identity_revealed': 'false',
                'voice_type': 'normal'
            }

        if args.file:
            try:
                f = open(args.file, 'rb')
                files = {'image': f}
            except Exception as e:
                print('Could not open file', args.file, e)
                return ('ERR', str(e), 0)

        status, text, elapsed = send_message(session, url, payload, files=files)

        if files:
            try:
                f.close()
            except Exception:
                pass

        return (status, text, elapsed)

    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(task, i) for i in range(total)]
        for future in as_completed(futures):
            status, text, elapsed = future.result()
            latencies.append(elapsed)
            if status == 200 or status == 302:
                successes += 1
            else:
                errors += 1

    duration = time.perf_counter() - start_time

    print('\nTest complete')
    print('Total requests:', total)
    print('Successes:', successes)
    print('Errors:', errors)
    print(f'Total time: {duration:.2f}s')
    if latencies:
        print('Requests/sec:', total / duration)
        print('Average latency (ms):', statistics.mean(latencies) * 1000)
        print('Median latency (ms):', statistics.median(latencies) * 1000)
        print('P95 latency (ms):', statistics.quantiles(latencies, n=100)[94] * 1000)
        print('P99 latency (ms):', statistics.quantiles(latencies, n=100)[98] * 1000)


if __name__ == '__main__':
    main()
