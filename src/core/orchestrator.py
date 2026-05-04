import json
import re
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.core.state_manager import AgentState
from src.prompts.router_prompt import ROUTER_PROMPT
from src.prompts.final_prompt import FINAL_PROMPT
from src.utils.logger import logger
import asyncio
from langsmith import traceable, trace as langsmith_trace

class Orchestrator:

    def __init__(self, agents: Dict[str, Any], llm):
        
        if not agents:
            logger.warning("[ORCHESTRATOR] Initialized without agents")
            raise Exception("No agents configured")

        self.agents = agents
        self.agent_names = list(self.agents.keys())
        self.agent_name_set = set(self.agent_names)
        self.max_steps = min(len(self.agent_names) * 2, 20)
        self.llm = llm

        logger.info(f"[ORCHESTRATOR] Initialized | agents={self.agent_names}")

        self.graph = self.build_graph()
        
        
    def _extract_json(self, text: str):

        text = re.sub(r"```json|```", "", text).strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)

        if match:
            return match.group(0)

        return text


    async def router_node(self, state: AgentState):

        query = state.get("user_query", "")
        available_agents = self.agent_names

        logger.info(f"[ORCHESTRATOR] Routing query | agents={available_agents}")

        agent_list_text = "\n".join([f"- {name}" for name in available_agents])
   
        routing_prompt = ROUTER_PROMPT.format(
            agent_list_text=agent_list_text,
            query=query,
            user_id=state["user_id"],
            client_id=state["client_id"]
        )   

        with langsmith_trace("Router Decision") as span:
            response = await self.llm.ainvoke(routing_prompt)
            raw_output = response.content.strip()

            try:
                clean_json = self._extract_json(raw_output)
                execution_plan: List[Dict[str, str]] = json.loads(clean_json)
            except Exception as e:
                logger.warning("[ORCHESTRATOR] Router failed to parse LLM output, using fallback plan")
                span.metadata["error"] = str(e)
                execution_plan = [
                    {"agent": available_agents[0], "query": query}
                ]

            span.metadata["query"] = query
            span.metadata["execution_plan"] = execution_plan
            span.metadata["raw_output"] = raw_output

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
            logger.warning("[ORCHESTRATOR] Empty execution plan after filtering, using fallback")
            filtered_plan = [
                {"agent": available_agents[0], "query": query}
            ]

        logger.info(f"[ORCHESTRATOR] Execution plan created | steps={len(filtered_plan)}")

        state["execution_plan"] = filtered_plan
        state["execution_index"] = 0
        trace = state.get("execution_trace") or []
        trace.append("router")
        state["execution_trace"] = trace

        return state

    
    def create_agent_node(self, agent):

        async def node(state: AgentState):

            current_index = state.get("execution_index", 0)
            plan = state.get("execution_plan") or []

            if current_index >= len(plan):
                return state

            trace = state.get("execution_trace") or []

            if trace and trace[-1] == agent.name:
                logger.warning(
                    f"[ORCHESTRATOR] Detected repeated agent execution: {agent.name}, skipping"
                )
                state["execution_index"] = current_index + 1
                return state
            
            if len(trace) >= 4 and trace[-2:] == trace[-4:-2]:
                logger.warning(
                    f"[ORCHESTRATOR] Oscillation loop detected: {trace[-4:]}, skipping"
                )
                state["execution_index"] = current_index + 1
                return state
            
            logger.info(
                f"[ORCHESTRATOR] Executing agent | name={agent.name}, step={current_index}"
            )

            with langsmith_trace(f"Agent: {agent.name}") as span:
                try:
                    result = await asyncio.wait_for(agent.run(state), timeout=15)
                    span.metadata["result_keys"] = list(result.keys()) if result else []
                except asyncio.TimeoutError:
                    logger.error(f"[ORCHESTRATOR] Agent timeout: {agent.name}")
                    span.metadata["timeout"] = True
                    result = {}
                except Exception as e:
                    logger.error(f"[ORCHESTRATOR] Agent failed: {agent.name} | error={str(e)}")
                    span.metadata["error"] = str(e)
                    result = {}

            trace.append(agent.name)

            state.update(result)
            state["execution_trace"] = trace
            state["execution_index"] = current_index + 1

            return state

        return node
    
    
    async def final_node(self, state: AgentState):

        query = state.get("user_query", "")

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
            logger.info("[ORCHESTRATOR] No data found for final response generation")
            state["final_response"] = "No relevant data found for the query."
            return state
        
        MAX_CONTEXT_ITEMS = 20

        if len(structured_context) > MAX_CONTEXT_ITEMS:
            logger.warning(
                f"[ORCHESTRATOR] Context too large ({len(structured_context)}), trimming to last {MAX_CONTEXT_ITEMS}"
            )
            structured_context = structured_context[-MAX_CONTEXT_ITEMS:]

        logger.info(f"[ORCHESTRATOR] Generating final response | context_size={len(structured_context)}")

        prompt = FINAL_PROMPT.format(
            query=query,
            structured_context=structured_context
        )

        with langsmith_trace("Final Response Generation") as span:
            span.metadata["context_size"] = len(structured_context)
            response = await self.llm.ainvoke(prompt)
        state["final_response"] = response.content

        logger.info("[ORCHESTRATOR] Final response generated")

        return state


    def build_graph(self):

        builder = StateGraph(AgentState)

        builder.add_node("router", self.router_node)

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

            if index >= self.max_steps:
                logger.warning(f"[ORCHESTRATOR] Max steps reached ({self.max_steps}), terminating execution")
                return "final"
          
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

        return builder.compile()


    @traceable(name="AMAO Pipeline")
    async def run(self, state: AgentState):
        logger.info("[ORCHESTRATOR] Execution started")
        result = await self.graph.ainvoke(state)
        logger.info("[ORCHESTRATOR]  Execution completed")
        return result