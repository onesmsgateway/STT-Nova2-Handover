import asyncio
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from chatbot.vector_store import VectorStore

async def debug_search():
    try:
        print('initializing vector store...')
        vector_store = VectorStore()
        queries = ['tổng số giáo viên', 'danh sách sách văn học', 'thư viện có những sách gì', 'hiệu trưởng là ai', 'nguyễn thị mai xuân']
        for q in queries:
            print(f"\n\n=== DEBUG SEARCH: '{q}' ===")
            results = await vector_store.search(q, school_code='10', limit=5)
            if not results:
                print(' -> NO RESULTS FOUND.')
            else:
                for idx, r in enumerate(results):
                    print(f"[{idx + 1}] Score: {r['similarity']:.4f}")
                    content = r.get('content', '')
                    print(f'      Content: \n{content}\n')
                    print(f"      Source: {r.get('filename', 'Unknown')}")
    except Exception as e:
        print(f'ERROR: {e}')
        import traceback
        traceback.print_exc()
if __name__ == '__main__':
    asyncio.run(debug_search())