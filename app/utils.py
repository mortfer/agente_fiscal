import os
from typing import Optional
from dotenv import load_dotenv
from langchain_core.utils.utils import secret_from_env
from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr
from langchain_core.messages import BaseMessage 
from pydantic import BaseModel
from fastapi import HTTPException, Request
import time
from app.logging_config import logger
load_dotenv()

class ChatOpenRouter(ChatOpenAI):
    openai_api_key: Optional[SecretStr] = Field(
        alias="api_key", default_factory=secret_from_env("OPENROUTER_API_KEY", default=None)
    )
    @property
    def lc_secrets(self) -> dict[str, str]:
        return {"openai_api_key": "OPENROUTER_API_KEY"}

    def __init__(self,
                 openai_api_key: Optional[str] = None,
                 **kwargs):
        openai_api_key = openai_api_key or os.environ.get("OPENROUTER_API_KEY")
        super().__init__(base_url="https://openrouter.ai/api/v1", openai_api_key=openai_api_key, **kwargs)
        
def custom_summarize_llm_input(state_dict: dict|BaseModel, internal_summarizer, n_last_messages) -> dict:
    if isinstance(state_dict, dict):
        original_messages = state_dict.get("messages")
        #context = state_dict.get("context", {})
    elif isinstance(state_dict, BaseModel):
        original_messages = getattr(state_dict, "messages", None)
        #context = getattr(state_dict, "context", {})
    else:
        raise ValueError(f"Invalid input type: {type(state_dict)}")
    messages_to_summarize_list = original_messages[:-n_last_messages]
    last_two_messages = original_messages[-n_last_messages:]
    summarized_messages_list: list[BaseMessage] = []
    
    state_update = {}
    if messages_to_summarize_list:
        state_dict["messages_to_summarize_input_key"] = messages_to_summarize_list
        try:
            summary_output_dict = internal_summarizer.invoke(state_dict)
            summarized_messages_list = summary_output_dict.get("summarized_part_output_key", [])
            state_update = summary_output_dict
        except Exception as e:
            print(f"Error al invocar el internal_summarizer: {e}")
            summarized_messages_list = messages_to_summarize_list 
       
    final_llm_input_list = summarized_messages_list + last_two_messages
    state_update["llm_input_messages"] = final_llm_input_list
    return state_update

class RateLimiter:
    request_counters = {} 
    def __init__(self, requests_limit: int, time_window: int, limit_type: str = "ip_path"):
        self.requests_limit = requests_limit
        self.time_window = time_window
        self.limit_type = limit_type

    async def __call__(self, request: Request):
        client_ip = request.client.host
        route_path = request.url.path
        current_time = int(time.time())

        if self.limit_type == "ip_path":
            key = f"ip:{client_ip}:{route_path}"
        elif self.limit_type == "global_path":
            key = f"global:{route_path}" 
        else: 
            raise ValueError("Invalid limit_type specified for RateLimiter")

        if key not in RateLimiter.request_counters:
            RateLimiter.request_counters[key] = {"timestamp": current_time, "count": 1}
        else:
            if current_time - RateLimiter.request_counters[key]["timestamp"] > self.time_window:
                RateLimiter.request_counters[key]["timestamp"] = current_time
                RateLimiter.request_counters[key]["count"] = 1
            else:
                if RateLimiter.request_counters[key]["count"] >= self.requests_limit:
                    
                    detail_msg = f"Too Many Requests. Limit type: {self.limit_type}"
                    if self.limit_type == "global_path":
                        logger.warning(f"Global rate limit hit for path {route_path}. Limit: {self.requests_limit}/{self.time_window}s. Current count: {RateLimiter.request_counters[key]['count']}")
                    raise HTTPException(status_code=429, detail=detail_msg)
                else:
                    RateLimiter.request_counters[key]["count"] += 1
            
        for k in list(RateLimiter.request_counters.keys()):
            if k.startswith(f"{self.limit_type.split('_')[0]}:"): 
                 if current_time - RateLimiter.request_counters[k]["timestamp"] > self.time_window:
                    RateLimiter.request_counters.pop(k, None)
        return True
