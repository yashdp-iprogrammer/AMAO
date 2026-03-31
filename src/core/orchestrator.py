import json
import re
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.core.state_manager import AgentState
from src.prompts.router_prompt import ROUTER_PROMPT
from src.prompts.final_prompt import FINAL_PROMPT


class Orchestrator:

    def __init__(self, agents: Dict[str, Any], llm):
        
        if not agents:
            raise Exception("No agents configured")
        self.agents = agents
        self.agent_names = list(self.agents.keys())
        self.agent_name_set = set(self.agent_names)
        self.llm = llm
        self.graph = self.build_graph()
        
        
    def _extract_json(self, text: str):

        text = re.sub(r"```json|```", "", text).strip()

        # extract JSON array
        match = re.search(r"\[.*\]", text, re.DOTALL)

        if match:
            return match.group(0)

        return text


    async def router_node(self, state: AgentState):

        query = state.get("user_query", "")

        available_agents = self.agent_names

        agent_list_text = "\n".join([f"- {name}" for name in available_agents])
   
        routing_prompt = ROUTER_PROMPT.format(
            agent_list_text=agent_list_text,
            query=query,
            user_id=state["user_id"],
            client_id=state["client_id"]
        )   

        response = await self.llm.ainvoke(routing_prompt)

        raw_output = response.content.strip()

        try:
            clean_json = self._extract_json(raw_output)
            execution_plan: List[Dict[str, str]] = json.loads(clean_json)
        except Exception:
            execution_plan = [
                {"agent": available_agents[0], "query": query}
            ]

        # Safety filtering
        filtered_plan = []
        for step in execution_plan:
            agent_name = step.get("agent")
            sub_query = step.get("query", query)

            if agent_name in self.agent_name_set:
                filtered_plan.append({
                    "agent": agent_name,
                    "query": sub_query
                })

        if not filtered_plan:
            filtered_plan = [
                {"agent": available_agents[0], "query": query}
            ]

        state["execution_plan"] = filtered_plan
        state["execution_index"] = 0
        state["execution_trace"] = state.get("execution_trace", []) + ["router"]

        # print("Execution Plan:", filtered_plan)

        return state


    def create_agent_node(self, agent):

        async def node(state: AgentState):

            current_index = state.get("execution_index", 0)
            plan = state.get("execution_plan", [])

            if current_index >= len(plan):
                return state

            result = await agent.run(state)

            trace = state.get("execution_trace", [])
            trace.append(agent.name)

            state.update(result)
            state["execution_trace"] = trace

            state["execution_index"] = current_index + 1

            return state

        return node
    
    
    async def final_node(self, state: AgentState):

        query = state.get("user_query", "")
        # sql_results = state.get("sql_results", [])
        # rag_results = state.get("rag_results", [])
        
        # if not sql_results and not rag_results:
        #     return {
        #         "response": "No relevant data found for the query."
        #     }
        
        structured_context = []

        for step in state.get("execution_plan", []):
            agent_name = step["agent"]
            results = state.get(agent_name + "_results", [])

            for result in results:
                structured_context.append({
                    "source": agent_name.upper(),
                    "query": result.get("query"),
                    "result": result.get("rows") or result.get("documents") or result
                })
        
        
        if not structured_context:
            state["final_response"] = "No relevant data found for the query."
            return state

        prompt = FINAL_PROMPT.format(
            query=query,
            structured_context=structured_context
        )

        response = await self.llm.ainvoke(prompt)
        state["final_response"] = response.content

        return state


    def build_graph(self):

        builder = StateGraph(AgentState)

        builder.add_node("router", self.router_node)

        # Add agent nodes
        for agent_name, agent in self.agents.items():
            builder.add_node(agent_name, self.create_agent_node(agent))

        builder.add_node("final", self.final_node)

        builder.set_entry_point("router")

        agent_names = self.agent_names


        def route_first_agent(state):
            plan = state.get("execution_plan", [])
            if plan:
                return plan[0]["agent"]
            return "final"

        router_mapping = {name: name for name in agent_names}
        router_mapping["final"] = "final"

        builder.add_conditional_edges(
            "router",
            route_first_agent,
            router_mapping
        )


        def route_next(state):
            plan = state.get("execution_plan", [])
            index = state.get("execution_index", 0)

            if index < len(plan):
                return plan[index]["agent"]

            return "final"

        agent_mapping = {name: name for name in agent_names}
        agent_mapping["final"] = "final"

        for agent_name in agent_names:
            builder.add_conditional_edges(
                agent_name,
                route_next,
                agent_mapping
            )

        builder.add_edge("final", END)

        self.graph = builder.compile()
    
    
    async def run(self, state: AgentState):
        return await self.graph.ainvoke(state)