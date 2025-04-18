from typing import Literal

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import Command
from langgraph.types import interrupt
from rich import get_console
from typing_extensions import TypedDict

###############
# Subgraph
###############


class SubGraphState(TypedDict, total=False):
    parent_counter: int
    sub_counter: int


def subgraph_accumulator(state: SubGraphState) -> SubGraphState:
    get_console().print("---subgraph counter node---")
    get_console().print(f"{state = }")
    # ask for human approval
    human_feedback = interrupt("get human feedback")
    print(f"{human_feedback = }")

    # continue counting
    sub_counter = state["sub_counter"] + 1 if "sub_counter" in state else 1
    return {"sub_counter": sub_counter}


sub_graph = (
    StateGraph(SubGraphState)
    .add_node(subgraph_accumulator)
    .add_edge(START, subgraph_accumulator.__name__)
    .add_edge(subgraph_accumulator.__name__, END)
    .compile(
        checkpointer=True,  # BUG: This causes an issue that subgraph nodes are not executed at all after first interruption
    )
)
sub_graph.name = "sub"


    

###############
# Parent Graph
###############

MAX_ITERATION = 3


class ParentGraphState(TypedDict):
    parent_counter: int



def sub_graph_node(state: ParentGraphState):
    parent_counter = state['parent_counter']
    subgraph_state = sub_graph.invoke({
        'parent_counter': parent_counter,
    })
    print(subgraph_state)
    return {
        'parent_counter': subgraph_state['parent_counter']
    }

def parent_graph_accumulator(
    state: ParentGraphState,
) -> Command[Literal["sub_node", "__end__"]]:
    print("---parent counter node---")
    get_console().print(f"{state = }")
    parent_counter = state["parent_counter"] + 1 if "parent_counter" in state else 0

    # goto end when max iteration reaches
    goto = 'sub_node' if parent_counter < MAX_ITERATION else END
    get_console().print("going to node sub_node")
    return Command(
        update={
            "parent_counter": parent_counter,
        },
        goto=goto,
    )

parent_agent = (
    StateGraph(ParentGraphState)
    .add_node('par_node', parent_graph_accumulator)
    .add_node('sub_node', sub_graph_node)
    .add_edge(START, 'par_node')
    .add_edge('sub_node', 'par_node')
    .compile(checkpointer=MemorySaver())
)

# visualize graph
# mermaid_graph = parent_agent.get_graph(xray=True).draw_mermaid()
# print(mermaid_graph)

###############
# Conversation
###############

config: RunnableConfig = {"configurable": {"thread_id": "42"}, "recursion_limit": MAX_ITERATION+1}

inputs = [
    ParentGraphState(parent_counter=0),
    Command(resume="human feedback 1"),
    Command(resume="human feedback 2"),
]
for input_ in inputs:
    print(f"{input_ = }")
    for event in parent_agent.stream(
        # resume the conversation
        input_,
        config,
        stream_mode="updates",
        subgraphs=True,
    ):
        print("Streaming event ...")
        print(event)