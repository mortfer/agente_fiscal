from dotenv import load_dotenv
import os
import logging
load_dotenv()
load_dotenv(".env.prompts")
from fastapi import FastAPI, HTTPException, Request, HTTPException, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from app.tools import regional_tax_deductions_details, list_regional_tax_deductions, internet_search_tool
import time
import os
import logging
from langchain.globals import set_verbose
set_verbose(True)
from langmem.short_term import SummarizationNode
from langgraph.prebuilt import create_react_agent
from app.tools import regional_tax_deductions_details, list_regional_tax_deductions, internet_search_tool
from langchain.chat_models import init_chat_model
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from typing import Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt.chat_agent_executor import AgentState, RunnableCallable
from langchain_core.messages import HumanMessage
import asyncio
import json
import aiosqlite 
from contextlib import asynccontextmanager 
from app.utils import custom_summarize_llm_input, RateLimiter
from functools import partial
from app.logging_config import logger

# Placeholder for memory, will be initialized on startup
memory: AsyncSqliteSaver | None = None
agent: Any = None 

class State(AgentState):
    context: dict[str, Any]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global memory, agent
    conn = await aiosqlite.connect("db/chatbot_memory.db")
    memory = AsyncSqliteSaver(conn=conn)
    await memory.setup()
    logging.info("AsyncSqliteSaver initialized and setup called.")
    llm = init_chat_model(model=os.getenv("LLM_MODEL"), model_provider=os.getenv("LLM_PROVIDER"), temperature=0.5)

    INITIAL_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
        [
            ("placeholder", "{messages}"),
            ("user", "Create a summary of the conversation above keeping the messages structure if possible:"),
        ]
    )
    max_summary_tokens = 256
    internal_summarizer = SummarizationNode( 
        token_counter=count_tokens_approximately,
        model=init_chat_model(model=os.getenv("LLM_MODEL"), model_provider=os.getenv("LLM_PROVIDER"),max_output_tokens=max_summary_tokens), # El mismo LLM o uno más pequeño para resumir
        max_tokens=3072, 
        max_tokens_before_summary=1024,
        max_summary_tokens=max_summary_tokens, 
        initial_summary_prompt=INITIAL_SUMMARY_PROMPT,
        input_messages_key="messages_to_summarize_input_key", 
        output_messages_key="summarized_part_output_key", 
    )

    summarizer = partial(custom_summarize_llm_input, internal_summarizer=internal_summarizer, n_last_messages=1)
    custom_summarizer_runnable = RunnableCallable(summarizer)
    
    agent_prompt_for_startup = ChatPromptTemplate.from_messages(
        [
            ("system", os.getenv("SYSTEM_TEMPLATE_AEAT")),
            MessagesPlaceholder(variable_name="messages"), 
        ]
    )
    tools_for_startup = [list_regional_tax_deductions, regional_tax_deductions_details, internet_search_tool]
    agent = create_react_agent(
        llm, 
        tools=tools_for_startup,
        prompt=agent_prompt_for_startup,
        state_schema=State, 
        checkpointer=memory,
        pre_model_hook=custom_summarizer_runnable,
    )
    logging.info("Agent re-initialized with AsyncSqliteSaver in lifespan startup.")
    
    yield 
    
    if memory and hasattr(memory, 'conn') and memory.conn:
        await memory.conn.close()
        logging.info("AsyncSqliteSaver connection closed during lifespan shutdown.")

app = FastAPI(title="Chat fiscal 2024", lifespan=lifespan)

router = APIRouter()

# Configure CORS
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost,http://localhost:8001,http://127.0.0.1,http://127.0.0.1:8001")
origins = [origin.strip() for origin in allowed_origins_str.split(',')]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

class ChatBody(BaseModel):       
    message: str
    thread_id: str
ip_rate_limiter_chat = RateLimiter(requests_limit=10, time_window=120, limit_type="ip_path")
global_rate_limiter_chat = RateLimiter(requests_limit=60, time_window=3600, limit_type="global_path")
@router.post("/chat", dependencies=[Depends(ip_rate_limiter_chat), Depends(global_rate_limiter_chat)])
async def chat(body: ChatBody):
    if not memory or not agent: 
        raise HTTPException(status_code=503, detail="Memory Saver or Agent not initialized.")
    dynamic_config = {
        "configurable": {
            "thread_id": body.thread_id
        }
    }
    async def event_stream():
        try:
            logging.debug(f"Starting agent.astream for thread_id: {body.thread_id} with AsyncSqliteSaver")
            async for chunk in agent.astream(
                {"messages": [HumanMessage(content=body.message)]},
                config=dynamic_config
            ):
                logging.debug(f"Raw chunk from agent.astream: {chunk}")
                token_to_send = None

                # Check for AIMessage content within an 'agent' chunk
                if "agent" in chunk and isinstance(chunk["agent"], dict) and "messages" in chunk["agent"]:
                    agent_messages = chunk["agent"]["messages"]
                    if agent_messages and isinstance(agent_messages, list) and len(agent_messages) > 0:
                        last_agent_message = agent_messages[-1]
                        # Ensure it's an AIMessage and has non-empty content
                        if hasattr(last_agent_message, 'content') and isinstance(last_agent_message.content, str) and last_agent_message.content.strip():
                            token_to_send = last_agent_message.content # Send the full content of this AIMessage
                            logging.debug(f"Extracted AIMessage content from chunk['agent']['messages'][-1].content: '{token_to_send}'")
                
                #Add handling for 'tools' chunks here if wanted

                if token_to_send: 
                    data_to_send = {"token": token_to_send}
                    yield f"data: {json.dumps(data_to_send)}\n\n"
                    await asyncio.sleep(0.01)
                else:
                    logging.debug("No new displayable AIMessage content extracted from this chunk.")

            logging.debug(f"Finished agent.astream for thread_id: {body.thread_id}")
            
            # mock_sources = [
            #     {"title": "Portal AEAT - Deducciones Autonómicas", "url": "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-practico-renta/capitulo-16-deducciones-autonomicas.html"},
            # ]
            # if mock_sources: 
            #     sources_payload = json.dumps({"sources_used": mock_sources})
            #     yield f"data: {sources_payload}\n\n"
            
            end_event_payload = json.dumps({"event": "end"})
            yield f"data: {end_event_payload}\n\n"
        except Exception as e:
            logging.error(f"Error during stream for thread_id {body.thread_id}: {e}", exc_info=True)
            error_data = {"error": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

class GoodbyeBody(BaseModel):
    thread_id: str
@router.post("/goodbye")
async def goodbye(body: GoodbyeBody):
    thread_id_to_clear = body.thread_id
    logging.info(f"Received request to clear memory for thread_id: {thread_id_to_clear} (using SqliteSaver).")
    logging.warning(f"Automatic thread deletion for {thread_id_to_clear} is not actively performed with the current SqliteSaver setup. Conversation will persist in the DB.")
    return {"status": "request_logged_sqlite_no_delete_action", "thread_id": thread_id_to_clear,
            "message": "SqliteSaver is in use. Specific thread deletion is not automatically performed by this endpoint."}

@router.get("/health")
async def health_check():
    return {"status": "ok"}

app.include_router(router, prefix="/api")

#TODO: Add guardrails to the agent.