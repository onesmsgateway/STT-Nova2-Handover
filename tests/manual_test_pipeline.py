import asyncio
import sys
import os
sys.path.append(os.getcwd())
from src.services.pipeline_service import PipelineService
from src.core.config import DEBUG_MODE

async def main():
    print('🚀 Starting Manual Pipeline Test...')
    pipeline = PipelineService()
    await pipeline.initialize()
    test_urls = []
    if len(sys.argv) > 1:
        test_urls = sys.argv[1:]
    if not test_urls:
        print('⚠️ Please provide a URL argument to test. Usage: python tests/manual_test_pipeline.py <url>')
        print('✅ Pipeline initialized successfully. No URL to process.')
        return
    print(f'Processing {len(test_urls)} URLs...')
    results = await pipeline.process_request(test_urls)
    for res in results:
        print('\n' + '=' * 50)
        print(f"URL: {res.get('original_url')}")
        print(f"Status: {res.get('status')}")
        if res.get('status') == 'completed':
            print(f"Transcript ({len(res.get('transcript', ''))} chars): {res.get('transcript')[:100]}...")
            print(f"Summary: {res.get('summary')}")
            print(f"Topic: {res.get('call_topic')}")
        else:
            print(f"Error: {res.get('error')}")
    await pipeline.notifier.stop()
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nInterrupted.')