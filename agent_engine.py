# agent_engine.py
# Version 2.3 (FIXED)

import asyncio
import time
import ollama
from typing import List, Dict, AsyncGenerator
import traceback


class AgentEngine:
    def __init__(self, config, **kwargs):
        self.config = config
        self.log = kwargs.get('log_callback', lambda msg, lvl: print(f"[{lvl}] {msg}"))

        self.providers = {
            'ollama': True,
            'bionic': True,
            'lmstudio': True,
            'strata': True,
            'groq': bool(config.get('groq_api_key', '').strip()),
            'huggingface': bool(config.get('hf_api_key', '').strip()),
            'openrouter': bool(config.get('openrouter_api_key', '').strip()),
            'gemini': bool(config.get('gemini_api_key', '').strip()),
            'together': bool(config.get('together_api_key', '').strip())
        }

        self.log("=" * 60, "INFO")
        self.log("Agent engine v2.3 initialized", "SUCCESS")
        self.log("Available providers:", "INFO")
        for provider, active in self.providers.items():
            status = "OK" if active else "NO"
            self.log(f"  [{status}] {provider.upper()}", "INFO")
        self.log("=" * 60, "INFO")

        self._clients = {}
        self._init_clients()

    def _init_clients(self):
        from openai import AsyncOpenAI

        if self.providers.get('bionic'):
            self._clients['bionic'] = AsyncOpenAI(
                base_url=self.config.get('bionic_url', 'http://localhost:1235/v1'),
                api_key=self.config.get('bionic_api_key', 'lm-studio'),
                timeout=120.0
            )

        if self.providers.get('lmstudio'):
            self._clients['lmstudio'] = AsyncOpenAI(
                base_url=self.config.get('lmstudio_url', 'http://localhost:1234/v1'),
                api_key=self.config.get('lmstudio_api_key', 'lm-studio'),
                timeout=120.0
            )

        if self.providers.get('strata'):
            self._clients['strata'] = AsyncOpenAI(
                base_url=self.config.get('strata_url', 'http://127.0.0.1:47831/v1'),
                api_key=self.config.get('strata_api_key', 'strata'),
                timeout=120.0
            )

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
        if self.providers['groq']:
            return {"provider": "groq", "model": "llama-3.1-70b-versatile", "name": "Groq: Llama 70B (judge)"}
        elif self.providers['openrouter']:
            return {"provider": "openrouter", "model": "qwen/qwen-2.5-coder-32b-instruct:free", "name": "OpenRouter: Qwen 32B (judge)"}
        elif self.providers['together']:
            return {"provider": "together", "model": "Qwen/Qwen2.5-Coder-32B-Instruct", "name": "Together: Qwen 32B (judge)"}
        else:
            return {"provider": "ollama", "model": "qwen2.5-coder:14b", "name": "Ollama: Qwen 14B (judge)"}

    async def _query_ollama(self, model: str, messages: List[Dict], timeout: float = 120.0) -> str:
        loop = asyncio.get_running_loop()
        def do_request():
            return ollama.chat(model=model, messages=messages, options={"num_predict": 1000})
        response = await asyncio.wait_for(loop.run_in_executor(None, do_request), timeout=timeout)
        return response['message']['content']



    async def run_task(self, prompt: str, status_callback=None, mode: str = "full", model: str = None, provider: str = None) -> str:
        self.log("=" * 70, "INFO")
        self.log(f"TASK: {prompt[:80]}", "INFO")
        self.log(f"MODE: {mode}", "INFO")
        if model and provider:
            self.log(f"TARGET: {provider} / {model}", "INFO")
            candidates = [{"provider": provider, "model": model, "name": f"{provider}: {model}"}]
        else:
            candidates = self._get_candidates()
        self.log("=" * 70, "INFO")
        active_providers = set(c['provider'].upper() for c in candidates)
        self.log(f"Active providers: {', '.join(sorted(active_providers))}", "INFO")
        self.log(f"Total models: {len(candidates)}", "INFO")
        if status_callback:
            status_callback(f"Sending to {len(candidates)} models...")
        tasks = [self.get_code_response(c, prompt) for c in candidates]
        self.log("Parallel query...", "INFO")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_responses = []
        for res in results:
            if isinstance(res, Exception):
                self.log(f"[ERR] Critical: {res}", "ERROR")
            elif isinstance(res, dict) and res.get("code"):
                valid_responses.append(res)
            elif isinstance(res, dict):
                self.log(f"[WARN] {res['candidate']['name']}: {res.get('error')}", "WARN")
        self.log(f"Success: {len(valid_responses)} of {len(candidates)}", "INFO")
        if valid_responses:
            answered = [r['candidate']['name'] for r in valid_responses]
            self.log(f"Answered: {', '.join(answered)}", "SUCCESS")
        if not valid_responses:
            if status_callback:
                status_callback("All models failed")
            self.log("All models failed", "ERROR")
            return "All models failed. Check Debug log."
        if mode == "fast":
            winner = valid_responses[0]['candidate']['name']
            if status_callback:
                status_callback(f"Fast: {winner}")
            self.log(f"Fast: {winner}", "SUCCESS")
            return valid_responses[0]["code"]
        if len(valid_responses) == 1:
            if status_callback:
                status_callback("1 response")
            self.log("Only 1 response", "INFO")
            return valid_responses[0]["code"]
        if status_callback:
            status_callback("Judge...")
        judge_result = await self.judge_responses(prompt, valid_responses)
        if judge_result.get("code"):
            if status_callback:
                status_callback("Judge selected")
            return judge_result["code"]
        else:
            self.log("Judge failed, taking first", "WARN")
            if status_callback:
                status_callback("Taking first")
            return valid_responses[0]["code"]
    async def _query_openai_style(self, provider: str, model: str, messages: List[Dict], timeout: float = 60.0) -> str:
        client = self._clients.get(provider)
        if not client:
            raise Exception(f"Client {provider} not initialized")

        response = await asyncio.wait_for(
            client.chat.completions.create(model=model, messages=messages, temperature=0.3),
            timeout=timeout
        )
        return response.choices[0].message.content

    async def _query_gemini(self, model: str, messages: List[Dict], timeout: float = 60.0) -> str:
        import aiohttp

        api_key = self.config.get('gemini_api_key', '')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"x-goog-api-key": api_key}

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
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Gemini API error {response.status}: {error_text[:100]}")
                result = await response.json()
                return result['candidates'][0]['content']['parts'][0]['text']

    async def _query_huggingface(self, model: str, messages: List[Dict], timeout: float = 60.0) -> str:
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
        provider = candidate['provider']
        model = candidate['model']

        if provider == 'ollama':
            return await self._query_ollama(model, messages, timeout)
        elif provider in ['groq', 'openrouter', 'together', 'bionic', 'lmstudio', 'strata']:
            return await self._query_openai_style(provider, model, messages, timeout)
        elif provider == 'gemini':
            return await self._query_gemini(model, messages, timeout)
        elif provider == 'huggingface':
            return await self._query_huggingface(model, messages, timeout)
        else:
            raise Exception(f"Unknown provider: {provider}")

    async def get_code_response(self, candidate: Dict, prompt: str) -> Dict:
        provider = candidate['provider'].upper()
        model_name = candidate['name']

        self.log(f"[{provider}] {model_name}...", "INFO")

        messages = [
            {"role": "system", "content": "You are an expert programmer in Python and VBA. Write clean, efficient code. Return ONLY code without explanations."},
            {"role": "user", "content": prompt}
        ]

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                code = await self._query_model(candidate, messages, timeout=120.0)
                self.log(f"[OK] [{provider}] {model_name}: {len(code)} chars", "SUCCESS")
                return {"candidate": candidate, "code": code, "error": None}
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    self.log(f"[{provider}] Retry {attempt+2}/{max_retries+1}...", "WARN")
                    await asyncio.sleep(2)
                    continue
                self.log(f"[{provider}] {model_name}: TIMEOUT", "ERROR")
                return {"candidate": candidate, "code": None, "error": "Timeout"}
            except Exception as e:
                self.log(f"[ERR] [{provider}] {model_name}: {str(e)[:60]}", "ERROR")
                return {"candidate": candidate, "code": None, "error": str(e)}

    async def judge_responses(self, prompt: str, responses: List[Dict]) -> Dict:
        judge = self._get_judge_model()
        provider = judge['provider'].upper()
        self.log(f"[JUDGE] [{provider}] Analyzing {len(responses)} responses...", "INFO")

        candidates_text = "\n\n".join([
            f"=== VARIANT #{i+1} ({r['candidate']['name']}) ===\n{r['code']}"
            for i, r in enumerate(responses)
        ])

        judge_prompt = f"""You are an expert programmer and judge. Choose the best variant.

TASK: {prompt}

VARIANTS:
{candidates_text}

CRITERIA: correctness, logic, completeness, readability.

Return ONLY the code of the best variant WITHOUT markdown and explanations.

ANSWER (code only):"""

        messages = [{"role": "user", "content": judge_prompt}]

        try:
            best_code = await self._query_model(judge, messages, timeout=120.0)
            self.log(f"[OK] [{provider}] Judge selected: {len(best_code)} chars", "SUCCESS")
            return {"code": best_code, "error": None, "judge": judge}
        except Exception as e:
            self.log(f"[ERR] [{provider}] Judge error: {str(e)[:60]}", "ERROR")
            return {"code": None, "error": str(e), "judge": judge}

    async def stream_task(self, prompt: str, mode: str = "fast", model: str = None, provider: str = None, system_prompt: str = None) -> AsyncGenerator[Dict, None]:
        start_time = time.perf_counter()
        first_token_time = None
        total_chars = 0

        target_provider = (provider or "ollama").lower()
        target_model = (model or "").strip()

        if target_provider == "all" and not target_model:
            candidates = self._get_candidates()
            if candidates:
                target_provider = candidates[0]["provider"]
                target_model = candidates[0]["model"]
            else:
                target_provider = "ollama"
                target_model = "qwen2.5-coder:1.5b"
        elif not target_model:
            if target_provider in ("bionic", "lmstudio", "strata"):
                try:
                    client = self._clients.get(target_provider)
                    if client:
                        models_resp = await client.models.list()
                        chat_models = [m.id for m in (models_resp.data or []) if 'embed' not in m.id.lower()]
                        if chat_models:
                            target_model = chat_models[0]
                        elif models_resp.data:
                            target_model = models_resp.data[0].id
                except Exception:
                    pass
                if not target_model:
                    target_model = "default"
            else:
                candidates = [c for c in self._get_candidates() if c["provider"] == target_provider]
                target_model = candidates[0]["model"] if candidates else "qwen2.5-coder:1.5b"

        sys_msg = (system_prompt or "").strip() or "You are a helpful AI assistant and expert programmer. Answer clearly and concisely in the user's language. When writing code, return clean code without markdown code fences."
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt}
        ]

        self.log(f"[STREAM] {target_provider} / {target_model}", "INFO")

        try:
            if target_provider == "ollama":
                queue: asyncio.Queue = asyncio.Queue()
                loop = asyncio.get_running_loop()
                stop_flag = {"stop": False}

                def worker():
                    try:
                        stream = ollama.chat(model=target_model, messages=messages, stream=True, options={"num_predict": 2048})
                        for part in stream:
                            if stop_flag["stop"]:
                                break
                            chunk = part.get("message", {}).get("content", "")
                            if chunk:
                                loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
                        loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
                    except Exception as err:
                        loop.call_soon_threadsafe(queue.put_nowait, ("error", str(err)))

                fut = loop.run_in_executor(None, worker)
                try:
                    while True:
                        kind, val = await queue.get()
                        if kind == "chunk":
                            if first_token_time is None:
                                first_token_time = time.perf_counter() - start_time
                            total_chars += len(val)
                            yield {"type": "chunk", "content": val}
                        elif kind == "error":
                            raise Exception(val)
                        elif kind == "done":
                            break
                finally:
                    stop_flag["stop"] = True
                    if not fut.done():
                        fut.cancel()

            elif target_provider in ("groq", "openrouter", "together", "bionic", "lmstudio", "strata"):
                client = self._clients.get(target_provider)
                if not client:
                    raise Exception(f"Client {target_provider} not initialized")
                stream = await client.chat.completions.create(
                    model=target_model,
                    messages=messages,
                    temperature=0.3,
                    stream=True
                )
                async for part in stream:
                    delta = part.choices[0].delta.content if part.choices else None
                    if delta:
                        if first_token_time is None:
                            first_token_time = time.perf_counter() - start_time
                        total_chars += len(delta)
                        yield {"type": "chunk", "content": delta}
            else:
                res = await self.run_task(prompt, mode=mode, model=target_model, provider=target_provider)
                first_token_time = time.perf_counter() - start_time
                total_chars = len(res or "")
                yield {"type": "chunk", "content": res or ""}

            elapsed = max(time.perf_counter() - start_time, 0.001)
            est_tokens = max(1, total_chars // 4)
            yield {
                "type": "meta",
                "provider": target_provider,
                "model": target_model,
                "elapsed_sec": round(elapsed, 2),
                "ttft_sec": round(first_token_time or elapsed, 2),
                "tokens": est_tokens,
                "tps": round(est_tokens / elapsed, 1)
            }
            yield {"type": "done"}
        except asyncio.CancelledError:
            self.log(f"[STREAM] Cancelled: {target_provider}/{target_model}", "WARN")
            raise
        except Exception as e:
            self.log(f"[STREAM ERR] {str(e)[:120]}", "ERROR")
            yield {"type": "error", "error": str(e)}

    async def _resolve_default_model(self, provider: str) -> str:
        prov = (provider or "ollama").lower()
        if prov == "ollama":
            try:
                loop = asyncio.get_running_loop()
                listed = await loop.run_in_executor(None, ollama.list)
                models = listed.get("models", []) if isinstance(listed, dict) else getattr(listed, "models", [])
                for m in models:
                    name = m.get("name") if isinstance(m, dict) else getattr(m, "model", "")
                    if name and "embed" not in name.lower():
                        return name
            except Exception:
                pass
            return "qwen2.5-coder:14b"
        if prov in ("bionic", "lmstudio", "strata"):
            try:
                client = self._clients.get(prov)
                if client:
                    resp = await client.models.list()
                    chat_models = [m.id for m in (resp.data or []) if "embed" not in m.id.lower()]
                    if chat_models:
                        return chat_models[0]
                    if resp.data:
                        return resp.data[0].id
            except Exception:
                pass
            return "default"
        candidates = [c for c in self._get_candidates() if c["provider"] == prov]
        return candidates[0]["model"] if candidates else "qwen2.5-coder:14b"

    async def stream_council(self, prompt: str, agents: List[Dict], judge: Dict = None) -> AsyncGenerator[Dict, None]:
        start_time = time.perf_counter()
        active_agents = [a for a in (agents or []) if a.get("enabled", True)]
        if not active_agents:
            yield {"type": "error", "error": "Нет активных агентов для консилиума"}
            return

        self.log(f"[COUNCIL] Starting with {len(active_agents)} agents", "INFO")
        yield {"type": "status", "content": f"⏳ Консилиум: параллельный опрос {len(active_agents)} агентов..."}

        async def ask_agent(ag: Dict) -> Dict:
            t0 = time.perf_counter()
            name = ag.get("name") or "Agent"
            prov = (ag.get("provider") or "ollama").lower()
            if prov == "all":
                prov = "ollama"
            mdl = (ag.get("model") or "").strip()
            if not mdl:
                mdl = await self._resolve_default_model(prov)
            sys_msg = (ag.get("systemPrompt") or ag.get("system_prompt") or "").strip() or (
                "You are a helpful AI assistant and expert engineer. Answer clearly and concisely in the user's language."
            )
            messages = [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt}
            ]
            try:
                text = await self._query_model({"provider": prov, "model": mdl, "name": name}, messages, timeout=120.0)
                elapsed = round(time.perf_counter() - t0, 2)
                self.log(f"[COUNCIL OK] {name} ({prov}/{mdl}) in {elapsed}s", "SUCCESS")
                return {"name": name, "provider": prov, "model": mdl, "elapsed_sec": elapsed, "content": text, "error": None}
            except Exception as err:
                elapsed = round(time.perf_counter() - t0, 2)
                self.log(f"[COUNCIL ERR] {name}: {str(err)[:100]}", "ERROR")
                return {"name": name, "provider": prov, "model": mdl, "elapsed_sec": elapsed, "content": None, "error": str(err)}

        tasks = [asyncio.create_task(ask_agent(ag)) for ag in active_agents]
        valid_responses = []
        try:
            for fut in asyncio.as_completed(tasks):
                res = await fut
                yield {"type": "agent_done", **res}
                if res.get("content"):
                    valid_responses.append(res)
        except asyncio.CancelledError:
            for t in tasks:
                if not t.done():
                    t.cancel()
            raise

        if not valid_responses:
            yield {"type": "error", "error": "Ни один из активных агентов не смог сформировать ответ"}
            return

        if len(valid_responses) == 1:
            only = valid_responses[0]
            total_elapsed = max(time.perf_counter() - start_time, 0.001)
            est_tokens = max(1, len(only["content"]) // 4)
            yield {"type": "single_winner", "name": only["name"], "content": only["content"]}
            yield {
                "type": "meta",
                "provider": only["provider"],
                "model": only["model"],
                "elapsed_sec": round(total_elapsed, 2),
                "ttft_sec": only["elapsed_sec"],
                "tokens": est_tokens,
                "tps": round(est_tokens / total_elapsed, 1)
            }
            yield {"type": "done"}
            return

        if judge and isinstance(judge, dict):
            j_name = judge.get("name") or "Judge"
            j_prov = (judge.get("provider") or "ollama").lower()
            if j_prov == "all":
                j_prov = "ollama"
            j_mdl = (judge.get("model") or "").strip() or await self._resolve_default_model(j_prov)
            j_sys = (judge.get("systemPrompt") or judge.get("system_prompt") or "").strip()
        else:
            fallback_j = self._get_judge_model()
            j_name = fallback_j["name"]
            j_prov = fallback_j["provider"]
            j_mdl = fallback_j["model"]
            j_sys = ""

        yield {"type": "status", "content": f"⚖️ Судья ({j_name} • {j_prov}/{j_mdl}) анализирует {len(valid_responses)} ответов..."}

        variants_block = "\n\n".join([
            f"=== ОТВЕТ АГЕНТА #{i+1}: {r['name']} ({r['provider']}/{r['model']}) ===\n{r['content']}"
            for i, r in enumerate(valid_responses)
        ])
        judge_instruction = (
            f"{j_sys}\n\n" if j_sys else ""
        ) + (
            "Ты выступаешь в роли Судьи консилиума ИИ-агентов. Проанализируй предложенные ниже ответы на задачу пользователя, "
            "сравни их по точности, полноте, логике и практической пользе. Сформируй лучший итоговый ответ (выбери сильнейший вариант или объедини лучшие части, исправив возможные неточности). "
            "Отвечай на языке пользователя чётко и по делу.\n\n"
            f"ЗАДАЧА ПОЛЬЗОВАТЕЛЯ:\n{prompt}\n\n"
            f"ВАРИАНТЫ АГЕНТОВ:\n{variants_block}\n\n"
            "ИТОГОВЫЙ ВЕРДИКТ СУДЬИ:"
        )

        judge_messages = [{"role": "user", "content": judge_instruction}]
        judge_t0 = time.perf_counter()
        first_token_time = None
        judge_chars = 0

        try:
            if j_prov in ("groq", "openrouter", "together", "bionic", "lmstudio", "strata") and self._clients.get(j_prov):
                client = self._clients[j_prov]
                stream = await client.chat.completions.create(
                    model=j_mdl,
                    messages=judge_messages,
                    temperature=0.2,
                    stream=True
                )
                async for part in stream:
                    delta = part.choices[0].delta.content if part.choices else None
                    if delta:
                        if first_token_time is None:
                            first_token_time = time.perf_counter() - judge_t0
                        judge_chars += len(delta)
                        yield {"type": "judge_chunk", "judge_name": j_name, "content": delta}
            else:
                verdict = await self._query_model({"provider": j_prov, "model": j_mdl, "name": j_name}, judge_messages, timeout=120.0)
                first_token_time = time.perf_counter() - judge_t0
                judge_chars = len(verdict or "")
                yield {"type": "judge_chunk", "judge_name": j_name, "content": verdict or ""}

            total_elapsed = max(time.perf_counter() - start_time, 0.001)
            est_tokens = max(1, judge_chars // 4)
            yield {
                "type": "meta",
                "provider": f"council→{j_prov}",
                "model": j_mdl,
                "elapsed_sec": round(total_elapsed, 2),
                "ttft_sec": round(first_token_time or total_elapsed, 2),
                "tokens": est_tokens,
                "tps": round(est_tokens / max(time.perf_counter() - judge_t0, 0.001), 1)
            }
            yield {"type": "done"}
        except Exception as e:
            self.log(f"[COUNCIL JUDGE ERR] {str(e)[:120]}", "ERROR")
            yield {"type": "error", "error": f"Ошибка судьи ({j_name}): {str(e)}"}

    async def stream_pipeline(self, prompt: str, steps: List[Dict]) -> AsyncGenerator[Dict, None]:
        start_time = time.perf_counter()
        valid_steps = [s for s in (steps or []) if isinstance(s, dict)]
        if not valid_steps:
            yield {"type": "error", "error": "В цепочке нет ни одного шага"}
            return

        total_steps = len(valid_steps)
        self.log(f"[PIPELINE] Starting {total_steps}-step pipeline", "INFO")
        previous_output = ""
        total_chars = 0
        first_token_time = None
        last_prov = "ollama"
        last_mdl = "default"

        try:
            for idx, step in enumerate(valid_steps):
                step_num = idx + 1
                name = step.get("name") or f"Шаг {step_num}"
                prov = (step.get("provider") or "ollama").lower()
                if prov == "all":
                    prov = "ollama"
                mdl = (step.get("model") or "").strip()
                if not mdl:
                    mdl = await self._resolve_default_model(prov)
                last_prov = prov
                last_mdl = mdl

                sys_msg = (step.get("systemPrompt") or step.get("system_prompt") or "").strip() or (
                    "You are a helpful AI assistant and expert engineer. Answer clearly and concisely in the user's language."
                )
                step_instr = (step.get("instruction") or "").strip()

                if idx == 0:
                    step_user_prompt = f"{prompt}\n\nИнструкция этапа: {step_instr}" if step_instr else prompt
                else:
                    extra = f"\n\nИнструкция текущего этапа ({name}): {step_instr}" if step_instr else ""
                    step_user_prompt = (
                        f"ИСХОДНАЯ ЗАДАЧА ПОЛЬЗОВАТЕЛЯ:\n{prompt}\n\n"
                        f"РЕЗУЛЬТАТ ПРЕДЫДУЩЕГО ЭТАПА:\n{previous_output}{extra}\n\n"
                        "Выполни свою часть работы на основе результата предыдущего этапа:"
                    )

                messages = [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": step_user_prompt}
                ]

                step_t0 = time.perf_counter()
                step_chunks: List[str] = []
                yield {
                    "type": "step_start",
                    "step": step_num,
                    "total": total_steps,
                    "name": name,
                    "provider": prov,
                    "model": mdl
                }

                if prov == "ollama":
                    queue: asyncio.Queue = asyncio.Queue()
                    loop = asyncio.get_running_loop()
                    stop_flag = {"stop": False}

                    def worker(m_name=mdl, msgs=messages, q=queue, sf=stop_flag):
                        try:
                            stream = ollama.chat(model=m_name, messages=msgs, stream=True, options={"num_predict": 2048})
                            for part in stream:
                                if sf["stop"]:
                                    break
                                chunk = part.get("message", {}).get("content", "")
                                if chunk:
                                    loop.call_soon_threadsafe(q.put_nowait, ("chunk", chunk))
                            loop.call_soon_threadsafe(q.put_nowait, ("done", None))
                        except Exception as err:
                            loop.call_soon_threadsafe(q.put_nowait, ("error", str(err)))

                    fut = loop.run_in_executor(None, worker)
                    try:
                        while True:
                            kind, val = await queue.get()
                            if kind == "chunk":
                                if first_token_time is None:
                                    first_token_time = time.perf_counter() - start_time
                                total_chars += len(val)
                                step_chunks.append(val)
                                yield {"type": "step_chunk", "step": step_num, "content": val}
                            elif kind == "error":
                                raise Exception(val)
                            elif kind == "done":
                                break
                    finally:
                        stop_flag["stop"] = True
                        if not fut.done():
                            fut.cancel()

                elif prov in ("groq", "openrouter", "together", "bionic", "lmstudio", "strata") and self._clients.get(prov):
                    client = self._clients[prov]
                    stream = await client.chat.completions.create(
                        model=mdl,
                        messages=messages,
                        temperature=0.3,
                        stream=True
                    )
                    async for part in stream:
                        delta = part.choices[0].delta.content if part.choices else None
                        if delta:
                            if first_token_time is None:
                                first_token_time = time.perf_counter() - start_time
                            total_chars += len(delta)
                            step_chunks.append(delta)
                            yield {"type": "step_chunk", "step": step_num, "content": delta}
                else:
                    res_text = await self._query_model({"provider": prov, "model": mdl, "name": name}, messages, timeout=120.0)
                    if first_token_time is None:
                        first_token_time = time.perf_counter() - start_time
                    total_chars += len(res_text or "")
                    step_chunks.append(res_text or "")
                    yield {"type": "step_chunk", "step": step_num, "content": res_text or ""}

                previous_output = "".join(step_chunks).strip()
                step_elapsed = round(time.perf_counter() - step_t0, 2)
                self.log(f"[PIPELINE STEP {step_num}/{total_steps} OK] {name} in {step_elapsed}s", "SUCCESS")
                yield {"type": "step_done", "step": step_num, "total": total_steps, "name": name, "elapsed_sec": step_elapsed}

            total_elapsed = max(time.perf_counter() - start_time, 0.001)
            est_tokens = max(1, total_chars // 4)
            yield {
                "type": "meta",
                "provider": f"pipeline({total_steps})→{last_prov}",
                "model": last_mdl,
                "elapsed_sec": round(total_elapsed, 2),
                "ttft_sec": round(first_token_time or total_elapsed, 2),
                "tokens": est_tokens,
                "tps": round(est_tokens / total_elapsed, 1)
            }
            yield {"type": "done"}
        except asyncio.CancelledError:
            self.log("[PIPELINE] Cancelled", "WARN")
            raise
        except Exception as e:
            self.log(f"[PIPELINE ERR] {str(e)[:120]}", "ERROR")
            yield {"type": "error", "error": str(e)}
