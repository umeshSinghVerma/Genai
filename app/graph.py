import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Send
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, ToolMessage,SystemMessage
from langchain_core.tools import tool
# from langchain_groq import ChatGroq
from transformers import AutoTokenizer, AutoModel
from pymilvus import connections, Collection
import torch


# from  import CHATBOT_PROMPT,VECTOR_DB_TOOL_PROMPT
from app.prompts import CHATBOT_PROMPT, GENERATE_RESPONSE_PROMPT

load_dotenv()
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# llm = ChatGroq(
#     model="llama-3.1-8b-instant",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
#     api_key=GROQ_API_KEY
# )
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")
MILVUS_URI = os.getenv("MILVUS_URI")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)

milvus_uri = MILVUS_URI
token = MILVUS_TOKEN
connections.connect("default", uri=milvus_uri, token=token)

collection_name = "knowledge_base"
collection = Collection(collection_name)

# Create index if not present
if not collection.has_index():
    index_params = {
        "metric_type": "IP",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 1024}
    }
    collection.create_index(field_name="embedding", index_params=index_params)

# Load collection
collection.load()
print("✅ Milvus collection loaded and ready.")

tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

import requests


def embed_text(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        embeddings = model(**inputs).last_hidden_state.mean(dim=1).numpy()
    return embeddings.flatten().tolist()


class State(MessagesState):
    pass 

def embed_text(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        embeddings = model(**inputs).last_hidden_state.mean(dim=1).numpy()
    return embeddings.flatten().tolist()

@tool
async def call_db_tool(query: str) -> str:
    """
    You are an agent specialized in querying a restaurant database.
    You will be given an input query that contains:
    The restaurant name (example: Punjab Grill, McDonald's, Burger King).
    Specific data needs (example: all veg dishes, price range, non-veg menu, cheapest items, etc.).
    Your task:
    Understand the specific request carefully.
    Query the vector database to retrieve only the information needed (no extra data).
    Return results in a simple, clear, and structured format.

    """
    return """
        "isBestseller": false,
            "price": 238,
            "priceCurrency": "INR",
            "description": "Delightfully crispy chicken sandwich with a crispy chicken patty topped with mayonnaise and ... read more",
            "isVeg": "non-veg",
            "dietary_tags": [],
            "menu_category": "main_course",
            "normalized_name": "mcchicken double patty burger",
            "ingredients": [],
            "spice_level": null,
            "processed_at": "2025-04-26T08:42:32.665548+00:00"
        },
    """


async def call_db(input):
    # print("insidesdb------->",input)
    query = input['args']['query']
    tool_call_id = input['id']
    print("query",query)

    query_embedding = embed_text(query)
    all_retrieved_docs = set()
    search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
    
    for _ in range(1):
        results = collection.search(
            [query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=10,
            output_fields=["content"]
        )
        for hits in results:
            for hit in hits:
                content = hit.get("content")
                if content:
                    all_retrieved_docs.add(content)
                    
    if not all_retrieved_docs:
    # Return an error-like message for LangGraph (cannot use jsonify)
        return {
            "messages": [ToolMessage(content="No relevant documents found for your query.", tool_call_id=tool_call_id)]
        }

    # Cap total docs to avoid overly large context
    selected_docs = list(all_retrieved_docs)[:4]
    
    print("query ",query)
    
    context = "Query : "+ query  + " Respose : "+"\n\n".join(selected_docs)
    # print(context)
    
    
    
    
    return {"messages": [ToolMessage(content=context, tool_call_id=tool_call_id)]}

async def chatbot(state: State):
    tools=[call_db_tool]
    
    finalMessages = [SystemMessage(CHATBOT_PROMPT)] + state['messages']

    tool_call_llm = llm.bind_tools(tools)
    
    response = await tool_call_llm.ainvoke(finalMessages)

    return {"messages": [response]}

async def combine_node(state:State):
    return 


async def generate_response(state: State):
    messages = state['messages']

    # Find the last human message (FIXED)
    human_message = next((msg for msg in reversed(messages) if isinstance(msg, HumanMessage)), None)
    if human_message is None:
        raise ValueError("No HumanMessage found.")

    # Find all ToolMessages after the human message
    tool_messages = []
    human_index = messages.index(human_message)
    for msg in messages[human_index + 1:]:
        if isinstance(msg, ToolMessage):
            tool_messages.append(msg.content)

    # Prepare the final human content
    tool_messages_text = "\n".join(tool_messages)  # join all tool messages
    final_human_content = tool_messages_text + "\n" + human_message.content

    print("final_message_", tool_messages_text, final_human_content)

    # Now create the final list
    final_messages = [
        SystemMessage(GENERATE_RESPONSE_PROMPT),
        HumanMessage(content=final_human_content)
    ]

    response = await llm.ainvoke(final_messages)
    return {"messages": [response]}

# Chatbot node router. Based on tool calls, creates the list of the next parallel nodes.
def assign_tool(state: State) -> list[Send] | str:
    # print("state_ass", state)
    messages = state["messages"]
    last_message = messages[-1]
    # print(last_message)
    if last_message.tool_calls:
        send_list = []
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == 'call_db_tool':
                send_list.append(Send('call_db', tool_call))
            elif tool_call["name"] == 'create_reminder_tool':
                send_list.append(Send('reminder', tool_call))
        return send_list if send_list else "__end__"
    return "__end__"


builder = StateGraph(State)



builder.add_node("chatbot", chatbot)
builder.add_node("call_db", call_db)
builder.add_node("combine_node", combine_node)
builder.add_node("generate_response", generate_response)

builder.add_edge(START, "chatbot")
builder.add_conditional_edges("chatbot", assign_tool)
builder.add_edge("call_db", "combine_node")
builder.add_edge("combine_node", "generate_response")
builder.add_edge("chatbot", END) 
builder.add_edge("generate_response", END)


memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
