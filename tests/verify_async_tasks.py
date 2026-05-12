import requests
import time
import uuid
BASE_URL = 'http://localhost:8000'

def test_async_webhook():
    print('🚀 Testing Async Webhook Pattern...')
    payload = {'recording_url': 'https://file-examples.com/storage/fe7e202534659b854653765/2017/11/file_example_WAV_1MG.wav', 'xml_cdr_uuid': str(uuid.uuid4()), 'direction': 'outbound', 'billsec': 60, 'duration': 65}
    print(f'📥 Sending webhook to {BASE_URL}/webhook...')
    response = requests.post(f'{BASE_URL}/webhook', json=payload)
    if response.status_code == 200:
        data = response.json()
        task_id = data.get('task_id')
        print(f'✅ Received 200 OK. Task ID: {task_id}')
    else:
        print(f'❌ Webhook failed with status {response.status_code}')
        print(response.text)
        return
    print(f'⏳ Polling task status for {task_id}...')
    for i in range(10):
        status_res = requests.get(f'{BASE_URL}/v1/tasks/{task_id}')
        if status_res.status_code == 200:
            task_data = status_res.json()
            status = task_data.get('status')
            print(f'[{i + 1}] Status: {status}')
            if status in ['completed', 'failed']:
                print('🎉 Task finished!')
                print(f"Result: {task_data.get('result')}")
                break
        else:
            print(f'❌ Failed to get status for {task_id}')
            break
        time.sleep(2)
if __name__ == '__main__':
    test_async_webhook()