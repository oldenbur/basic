
from langgraph.graph import StateGraph, START
from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator
import logging
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

async def work(node_name: str) -> MessagesState:
    logging.info(f"{node_name} - starting")
    await asyncio.sleep(3)
    logging.info(f"{node_name} - done")
    return {"messages": node_name}

async def node1(state: MessagesState):
    return await work("node1")

async def node2(state: MessagesState):
    return await work("node2")



agent_builder = StateGraph(MessagesState)

agent_builder.add_node("node1", node1)
agent_builder.add_node("node2", node2)

agent_builder.add_edge(START, "node1")
agent_builder.add_edge(START, "node2")

agent = agent_builder.compile()

messages = await agent.ainvoke({"messages": []})
for m in messages["messages"]:
    m.pretty_print()
