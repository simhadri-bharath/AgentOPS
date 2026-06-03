import asyncio
from deepeval.models.base_model import DeepEvalBaseLLM
from app.services.evaluation.agent_invoker import AgentInvoker

class PlatformAgentTargetLLM(DeepEvalBaseLLM):
    def __init__(self, endpoint_url: str, model_name: str = "agent-target", system_prompt: str = ""):
        self.endpoint_url = endpoint_url
        self._model_name = model_name
        self._system_prompt = system_prompt
        self._invoker = AgentInvoker()
        super().__init__(model_name)

    def load_model(self):
        return self._invoker

    def generate(self, prompt: str, *args, **kwargs) -> str:
        res = self._invoker.invoke_agent(
            self.endpoint_url,
            prompt,
            user_id="agentops_redteam",
        )
        if res.error:
            return ""
        return res.output or ""

    async def a_generate(self, prompt: str, *args, **kwargs) -> str:
        res = await asyncio.to_thread(
            self._invoker.invoke_agent,
            self.endpoint_url,
            prompt,
            user_id="agentops_redteam",
        )
        if res.error:
            return ""
        return res.output or ""

    def get_model_name(self) -> str:
        return self._model_name

    def get_system_prompt(self) -> str:
        return self._system_prompt
