import os
import sys
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config_loading():
    print('\n--------- 1. Config Loading Test ---------')
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print('✅ .env loaded')
    except ImportError:
        print('⚠️ dotenv not installed')
    import config
    print(f"WEBHOOK_DOMAIN_MAPPING (raw env): {os.getenv('WEBHOOK_DOMAIN_MAPPING')}")
    print(f'WEBHOOK_DOMAIN_MAPPING (parsed): {config.WEBHOOK_DOMAIN_MAPPING}')
    if not config.WEBHOOK_DOMAIN_MAPPING:
        print('❌ WEBHOOK_DOMAIN_MAPPING is empty! Check .env file.')
    else:
        print('✅ WEBHOOK_DOMAIN_MAPPING loaded successfully.')

def test_webhook_replacement():
    print('\n--------- 2. Webhook URL Replacement Test ---------')
    import config
    test_url = 'http://postgres-api:5002/api/ai/webhook'
    print(f'Original URL: {test_url}')
    if config.WEBHOOK_DOMAIN_MAPPING:
        for internal_host, target_domain in config.WEBHOOK_DOMAIN_MAPPING.items():
            if internal_host in test_url:
                search_str = f'http://{internal_host}'
                if search_str in test_url:
                    new_url = test_url.replace(search_str, target_domain)
                    print(f'✅ Replaced URL: {new_url}')
                    return
    print('❌ URL replacement FAILED. No match found or logic error.')

def test_gemini_models():
    print('\n--------- 3. Gemini Model List Test ---------')
    try:
        import google.generativeai as genai
        import config
        gui_keys = config.GOOGLE_API_KEYS
        if not gui_keys:
            print('❌ No GOOGLE_API_KEYS found.')
            return
        key = gui_keys[0]
        print(f'Using Key: {key[:8]}...')
        genai.configure(api_key=key)
        print('Fetching available models...')
        try:
            models = list(genai.list_models())
            print(f'Found {len(models)} models.')
            found_flash = False
            for m in models:
                if 'generateContent' in m.supported_generation_methods:
                    print(f' - {m.name}')
                    if 'gemini-1.5-flash' in m.name:
                        found_flash = True
            target_model = config.GOOGLE_AI_MODEL
            print(f'\nTarget Model from config: {target_model}')
            try:
                model = genai.GenerativeModel(target_model)
                print(f"✅ Model '{target_model}' initialized successfully.")
                resp = model.generate_content('Hello')
                print(f'✅ Generation Test: {resp.text.strip()}')
            except Exception as e:
                print(f"❌ Failed to initialize/generate with '{target_model}': {e}")
        except Exception as e:
            print(f'❌ Failed to list models: {e}')
    except ImportError:
        print('⚠️ google.generativeai not installed')
if __name__ == '__main__':
    print('=== Production Diagnostic Script ===')
    test_config_loading()
    test_webhook_replacement()
    test_gemini_models()
    print('\n=== End ===')