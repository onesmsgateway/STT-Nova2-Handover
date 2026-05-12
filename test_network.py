import socket
import requests
import os

def test_connectivity():
    print('🔍 Testing Network Connectivity...')
    targets = [('google.com', 80), ('api.telegram.org', 443), ('postgres-api', 5002), ('host.docker.internal', 5002)]
    for host, port in targets:
        try:
            print(f'\nTesting {host}:{port}...')
            ip = socket.gethostbyname(host)
            print(f'   ✅ DNS Resolved: {ip}')
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, port))
            if result == 0:
                print(f'   ✅ TCP Connect Success')
            else:
                print(f'   ❌ TCP Connect Failed (Error: {result})')
            sock.close()
        except Exception as e:
            print(f'   ❌ Failed: {e}')
if __name__ == '__main__':
    test_connectivity()