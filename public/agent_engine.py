# agent_engine.py
# Версия 2.3 (ИСПРАВЛЕНО)

import asyncio
import ollama
from typing import List, Dict
import traceback


class AgentEngine:
    def __init__(self, config, **kwargs):
        self.config = config
        self.log = kwargs.get('log_callback', lambda msg, lvl: print(f"[{lvl}] {msg}"))
        
        self.providers = {
            'ollama': True,
            'groq': bool(config.get('groq_api_key', '').strip()),
            'huggingface': bool(config.get('hf_api_key', '').strip()),
            'openrouter': bool(config.get('openrouter_api_key', '').strip()),
            'gemini': bool(config.get('gemini_api_key', '').strip()),
            'together': bool(config.get('together_api_key', '').strip())
        }
        
        self.log("=" * 60, "INFO")
        self.log("Инициализация ядра v2.3", "SUCCESS")
        self.log("Доступные провайдеры:", "INFO")
        for provider, active in self.providers.items():
            status = "✅" if active else "❌"
            self.log(f"  {status} {provider.upper()}", "INFO")
        self.log("=" * 60, "INFO")
        
        self._clients = {}
        self._init_clients()

    def _init_clients(self):
        """Инициализация клиентов"""
        from openai import AsyncOpenAI
        
        if self.providers['groq']:
            self._clients['groq'] = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.config.get('groq_api_key', ''),
                timeout=60.0
            )
        
        if self.providers['openrouter']:
            self._clients['openrouter'] = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.config.get('openrouter_api_key', ''),
                timeout=60.0
            )
        
        if self.providers['together']:
            self._clients['together'] = AsyncOpenAI(
                base_url="https://api.together.xyz/v1",
                api_key=self.config.get('together_api_key', ''),
                timeout=60.0
            )
        
        if self.providers['huggingface']:
            self._clients['huggingface'] = {
                'api_key': self.config.get('hf_api_key', ''),
                'timeout': 60.0
            }

    def _get_candidates(self) -> List[Dict]:
        """Возвращает список моделей из всех доступных провайдеров"""
        candidates = []
        
        if self.providers['ollama']:
            candidates.extend([
                {"provider": "ollama", "model": "qwen2.5-coder:1.5b", "name": "Ollama: Qwen 1.5B"},
                {"provider": "ollama", "model": "qwen2.5-coder:14b", "name": "Ollama: Qwen 14B"}
            ])
        
        if self.providers['groq']:
            candidates.extend([
                {"provider": "groq", "model": "llama-3.1-8b-versatile", "name": "Groq: Llama 8B"},
                {"provider": "groq", "model": "llama-3.1-70b-versatile", "name": "Groq: Llama 70B"}
            ])
        
        if self.providers['openrouter']:
            candidates.extend([
                {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct:free", "name": "OpenRouter: Llama 8B (free)"},
                {"provider": "openrouter", "model": "qwen/qwen-2.5-coder-32b-instruct:free", "name": "OpenRouter: Qwen 32B (free)"}
            ])
        
        if self.providers['gemini']:
            candidates.append({
                "provider": "gemini", 
                "model": "gemini-1.5-flash", 
                "name": "Gemini: 1.5 Flash"
            })
        
        if self.providers['together']:
            candidates.extend([
                {"provider": "together", "model": "meta-llama/Llama-3.1-8B-Instruct-Turbo", "name": "Together: Llama 8B"},
                {"provider": "together", "model": "Qwen/Qwen2.5-Coder-32B-Instruct", "name": "Together: Qwen 32B"}
            ])
        
        if self.providers['huggingface']:
            candidates.extend([
                {"provider": "huggingface", "model": "meta-llama/Llama-3.1-8B-Instruct", "name": "HF: Llama 8B"},
                {"provider": "huggingface", "model": "Qwen/Qwen2.5-Coder-32B-Instruct", "name": "HF: Qwen 32B"}
            ])
        
        return candidates

    def _get_judge_model(self) -> Dict:
        """Выбираем лучшую доступную модель для судьи"""
        if self.providers['groq']:
            return {"provider": "groq", "model": "llama-3.1-70b-versatile", "name": "Groq: Llama 70B (судья)"}
        elif self.providers['openrouter']:
            return {"provider": "openrouter", "model": "qwen/qwen-2.5-coder-32b-instruct:free", "name": "OpenRouter: Qwen 32B (судья)"}
        elif self.providers['together']:
            return {"provider": "together", "model": "Qwen/Qwen2.5-Coder-32B-Instruct", "name": "Together: Qwen 32B (судья)"}
        else:
            return {"provider": "ollama", "model": "qwen2.5-coder:14b", "name": "Ollama: Qwen 14B (судья)"}

    async def _query_ollama(self, model: str, messages: List[Dict], timeout: float = 120.0) -> str:
        loop = asyncio.get_running_loop()
        def do_request():
            return ollama.chat(model=model, messages=messages, options={"num_predict": 1000})
        response = await asyncio.wait_for(loop.run_in_executor(None, do_request), timeout=timeout)
        return response['message']['content']

    async def _query_openai_style(self, provider: str, model: str, messages: List[Dict], timeout: float = 60.0) -> str:
        """Универсальный запрос для OpenAI-совместимых API"""
        client = self._clients.get(provider)
        if not client:
            raise Exception(f"Клиент {provider} не инициализирован")
        
        response = await asyncio.wait_for(
            client.chat.completions.create(model=model, messages=messages, temperature=0.3),
            timeout=timeout
        )
        return response.choices[0].message.content

    async def _query_gemini(self, model: str, messages: List[Dict], timeout: float = 60.0) -> str:
        """Запрос к Google Gemini"""
        import aiohttp
        
        api_key = self.config.get('gemini_api_key', '')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1000
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Gemini API error {response.status}: {error_text[:100]}")
                result = await response.json()
                return result['candidates'][0]['content']['parts'][0]['text']

    async def _query_huggingface(self, model: str, messages: List[Dict], timeout: float = 60.0) -> str:
        """Запрос к HuggingFace Inference API"""
        import aiohttp
        api_key = self.config.get('hf_api_key', '')
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {api_key}"}
        prompt = messages[-1]['content']
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"inputs": prompt}, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"HF API error {resp.status}: {error_text[:100]}")
                result = await resp.json()
                return result[0]['generated_text']

    async def _query_model(self, candidate: Dict, messages: List[Dict], timeout: float = 120.0) -> str:
        """Универсальный диспетчер запросов"""
        provider = candidate['provider']
        model = candidate['model']
        
        if provider == 'ollama':
            return await self._query_ollama(model, messages, timeout)
        elif provider in ['groq', 'openrouter', 'together']:
            return await self._query_openai_style(provider, model, messages, timeout)
        elif provider == 'gemini':
            return await self._query_gemini(model, messages, timeout)
        elif provider == 'huggingface':
            return await self._query_huggingface(model, messages, timeout)
        else:
            raise Exception(f"Неизвестный провайдер: {provider}")

    async def get_code_response(self, candidate: Dict, prompt: str) -> Dict:
        """Запрос к одной модели с retry"""
        provider = candidate['provider'].upper()
        model_name = candidate['name']
        
        self.log(f"🚀 [{provider}] {model_name}...", "INFO")
        
        messages = [
            {"role": "system", "content": "You are an expert programmer in Python and VBA. Write clean, efficient code. Return ONLY code without explanations."},
            {"role": "user", "content": prompt}
        ]
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                code = await self._query_model(candidate, messages, timeout=120.0)
                self.log(f"✅ [{provider}] {model_name}: {len(code)} симв.", "SUCCESS")
                return {"candidate": candidate, "code": code, "error": None}
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    self.log(f"⏳ [{provider}] Попытка {attempt+2}/{max_retries+1}...", "WARN")
                    await asyncio.sleep(2)
                    continue
                self.log(f"⏱️ [{provider}] {model_name}: ТАЙМАУТ", "ERROR")
                return {"candidate": candidate, "code": None, "error": "Таймаут"}
            except Exception as e:
                self.log(f"❌ [{provider}] {model_name}: {str(e)[:60]}", "ERROR")
                return {"candidate": candidate, "code": None, "error": str(e)}

    async def judge_responses(self, prompt: str, responses: List[Dict]) -> Dict:
        """Судья с детальным логом"""
        judge = self._get_judge_model()
        provider = judge['provider'].upper()
        self.log(f"⚖️ [{provider}] Судья анализирует {len(responses)} ответов...", "INFO")
        
        candidates_text = "\n\n".join([
            f"=== ВАРИАНТ #{i+1} ({r['candidate']['name']}) ===\n{r['code']}"
            for i, r in enumerate(responses)
        ])
        
        judge_prompt = f"""Ты — эксперт-программист и судья. Выбери лучший вариант.

ЗАДАЧА: {prompt}

ВАРИАНТЫ:
{candidates_text}

КРИТЕРИИ: корректность, логика, полнота, читаемость.

Выведи ТОЛЬКО код лучшего варианта БЕЗ markdown и пояснений.

ОТВЕТ (только код):"""
        
        messages = [{"role": "user", "content": judge_prompt}]
        
        try:
            best_code = await self._query_model(judge, messages, timeout=120.0)
            self.log(f"🏆 [{provider}] Судья выбрал: {len(best_code)} симв.", "SUCCESS")
            return {"code": best_code, "error": None, "judge": judge}
        except Exception as e:
            self.log(f"❌ [{provider}] Судья ошибка: {str(e)[:60]}", "ERROR")
            return {"code": None, "error": str(e), "judge": judge}

    async def run_task(self, prompt: str, status_callback=None, mode: str = "full") -> str:
        self.log("=" * 70, "INFO")
        self.log(f"ЗАДАЧА: {prompt[:80]}", "INFO")
        self.log(f"РЕЖИМ: {mode}", "INFO")
        self.log("=" * 70, "INFO")
        
        candidates = self._get_candidates()
        active_providers = set(c['provider'].upper() for c in candidates)
        self.log(f"📋 Активные провайдеры: {', '.join(sorted(active_providers))}", "INFO")
        self.log(f"Всего моделей: {len(candidates)}", "INFO")
        
        if status_callback:
            status_callback(f"🚀 Отправка {len(candidates)} моделям...")
        
        tasks = [self.get_code_response(c, prompt) for c in candidates]
        self.log("⏳ Параллельный опрос...", "INFO")
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_responses = []
        for res in results:
            if isinstance(res, Exception):
                self.log(f"❌ Критическая ошибка: {res}", "ERROR")
            elif isinstance(res, dict) and res.get("code"):
                valid_responses.append(res)
            elif isinstance(res, dict):
                self.log(f"⚠️ {res['candidate']['name']}: {res.get('error')}", "WARN")
        
        self.log(f"📊 Успешных: {len(valid_responses)} из {len(candidates)}", "INFO")
        
        if valid_responses:
            answered = [r['candidate']['name'] for r in valid_responses]
            self.log(f"✅ Ответили: {', '.join(answered)}", "SUCCESS")
        
        if not valid_responses:
            if status_callback:
                status_callback("❌ Все молчат")
            self.log("💥 Все модели не ответили", "ERROR")
            return "Все модели не ответили. Проверь Debug лог."
        
        if mode == "fast":
            winner = valid_responses[0]['candidate']['name']
            if status_callback:
                status_callback(f"⚡ {winner}")
            self.log(f"⚡ Быстрый: {winner}", "SUCCESS")
            return valid_responses[0]["code"]
        
        if len(valid_responses) == 1:
            if status_callback:
                status_callback("⚡ 1 ответ")
            self.log("⚖️ Только 1 ответ", "INFO")
            return valid_responses[0]["code"]
        
        if status_callback:
            status_callback("⚖️ Судья...")
        judge_result = await self.judge_responses(prompt, valid_responses)
        
        if judge_result.get("code"):
            if status_callback:
                status_callback("🏆 Судья выбрал")
            return judge_result["code"]
        else:
            self.log("⚠️ Судья ошибся, берем первый", "WARN")
            if status_callback:
                status_callback("⚡ Берем первый")
            return valid_responses[0]["code"]
