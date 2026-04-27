import asyncio
import httpx


class VLLMRuntimeManager:

    def __init__(self, port_allocator):
        self.port_allocator = port_allocator
        self.running = {}
        self.locks = {}

    async def ensure(self, model_name: str):

        if model_name in self.running:
            return self.running[model_name]["base_url"]

        if model_name not in self.locks:
            self.locks[model_name] = asyncio.Lock()

        async with self.locks[model_name]:

            if model_name in self.running:
                return self.running[model_name]["base_url"]

            port = await self.port_allocator.get_port()
            base_url = f"http://localhost:{port}/v1"

            print(f"[VLLM] Starting model {model_name} on port {port}")
            
            
            process = await asyncio.create_subprocess_exec(
                    "python", "-m", "vllm.entrypoints.openai.api_server",
                    "--model", model_name,
                    "--port", str(port),
                    "--trust-remote-code",
                    "--dtype", "float16",
                    "--max-model-len", "2048",
                    "--gpu-memory-utilization", "0.75",
                    "--kv-cache-dtype", "fp8",
                    "--enforce-eager",
                    "--attention-backend", "triton_attn",
                    stdout=None,
                    stderr=asyncio.subprocess.PIPE,
                )

            await self._wait_ready(base_url, process)

            self.running[model_name] = {
                "base_url": base_url,
                "process": process
            }

            print(f"[VLLM] Model ready: {model_name}")

            return base_url

    async def _wait_ready(self, base_url, process, timeout=900):

        async with httpx.AsyncClient() as client:
            for _ in range(timeout):

                if process.returncode is not None:
                    err = await process.stderr.read()
                    raise RuntimeError(f"vLLM crashed:\n{err.decode()}")

                try:
                    r = await client.get(f"{base_url}/models", timeout=2)
                    if r.status_code == 200:
                        return
                except:
                    pass

                await asyncio.sleep(2)

        raise RuntimeError(f"vLLM failed to start at {base_url}")
    
    
    async def stop_all(self):
        """Kills all running vLLM instances."""
        for model_name, data in self.running.items():
            process = data["process"]
            print(f"[VLLM] Shutting down {model_name}...")
            try:
                process.terminate()
                # Wait up to 5 seconds for it to exit cleanly
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                print(f"[VLLM] {model_name} forced kill.")
                process.kill()
        self.running.clear()