import logging
from typing import List, Dict, Any

logger = logging.getLogger("workflow_engine")

# Agent display name mapping
AGENT_DISPLAY_NAMES = {
    "qa_doc_create": "QA Doc Creator",
    "qa_consult": "QA Consult",
    "qa_security_scan": "QA Security",
    "qa_research": "QA Research",
    "system": "🔧 System",
    "input": "📥 Input",
    "output": "📤 Output",
}

def agent_name(agent_type: str) -> str:
    return AGENT_DISPLAY_NAMES.get(agent_type, agent_type)

def make_msg(speaker: str, message: str, msg_type: str = "info") -> Dict:
    """Create a structured chat message dict."""
    return {
        "speaker": speaker,
        "message": message,
        "type": msg_type  # "info" | "speak" | "pass" | "error" | "system"
    }

def execute_agent(agent_type: str, input_data: str, params: Dict[str, Any]) -> str:
    """Executes a specific agent with the given input."""
    logger.info(f"Executing agent: {agent_type}")
    
    if agent_type == "qa_security_scan":
        from orchestrator.master_agent import qa_security_scan
        return qa_security_scan(source_code=input_data, language=params.get("language", "auto"), standard=params.get("standard", "OWASP Top 10 (2021)"))
        
    elif agent_type == "qa_consult":
        from orchestrator.master_agent import qa_consult
        return qa_consult(project_id=params.get("project_id", ""), instruction=input_data)
        
    elif agent_type == "qa_research":
        from orchestrator.master_agent import qa_research
        return qa_research(project_id=params.get("project_id", ""), question=input_data)
        
    elif agent_type == "qa_doc_create":
        from agent_6_doc_creator import create_qa_document
        project_id = params.get("project_id", "")
        skill_id = int(params.get("skill_id", "1"))
        doc_type = params.get("doc_type", "General Document")
        doc_name = params.get("doc_name", "Generated Doc")
        success, result = create_qa_document(project_id, doc_type, doc_name, skill_id)
        if success:
            return result
        return f"Doc Create Failed: {result}"
        
    return f"Unknown agent type: {agent_type}"


def execute_debate_loop(generator: str, critic: str, initial_input: str, params: Dict[str, Any], chat_logs: List[Dict]) -> str:
    """Runs an iterative debate between a generator and a critic."""
    max_loops = int(params.get("max_loops", 3))
    current_content = initial_input
    critic_feedback = ""

    gen_name = agent_name(generator)
    crit_name = agent_name(critic)
    
    chat_logs.append(make_msg("🔧 System", f"เริ่มต้น Debate Loop ระหว่าง **{gen_name}** และ **{crit_name}** (สูงสุด {max_loops} รอบ)", "system"))
    
    for i in range(max_loops):
        chat_logs.append(make_msg("🔧 System", f"— รอบที่ {i+1} / {max_loops} —", "system"))
        
        # 1. Generator phase
        if i == 0:
            gen_input = initial_input
        else:
            gen_input = f"Here is the previous draft:\n\n{current_content}\n\nCritic's feedback to address:\n\n{critic_feedback}"
        
        chat_logs.append(make_msg(gen_name, "⏳ กำลังสร้าง/แก้ไขเนื้อหา...", "info"))
        try:
            current_content = execute_agent(generator, gen_input, params)
        except Exception as e:
            chat_logs.append(make_msg(gen_name, f"❌ เกิดข้อผิดพลาด: {str(e)}", "error"))
            break
        
        preview = current_content[:500] + ("..." if len(current_content) > 500 else "")
        chat_logs.append(make_msg(gen_name, preview, "speak"))
        
        # 2. Critic phase
        critic_input = (
            f"Please critically evaluate the following content. "
            f"If it fully meets requirements, reply with exactly 'PASS' and nothing else. "
            f"Otherwise provide specific, actionable feedback for improvement.\n\n{current_content}"
        )
        
        chat_logs.append(make_msg(crit_name, "⏳ กำลังตรวจสอบและวิจารณ์...", "info"))
        try:
            critic_feedback = execute_agent(critic, critic_input, params)
        except Exception as e:
            chat_logs.append(make_msg(crit_name, f"❌ เกิดข้อผิดพลาด: {str(e)}", "error"))
            break

        critic_preview = critic_feedback[:500] + ("..." if len(critic_feedback) > 500 else "")
        chat_logs.append(make_msg(crit_name, critic_preview, "speak"))
        
        # 3. Check PASS
        if critic_feedback.strip().upper().startswith("PASS"):
            chat_logs.append(make_msg(crit_name, "✅ ผ่านการตรวจสอบแล้ว! งานเสร็จสมบูรณ์", "pass"))
            break
        elif i == max_loops - 1:
            chat_logs.append(make_msg("🔧 System", "⚠️ ครบจำนวนรอบสูงสุดแล้ว — ใช้ร่างล่าสุด", "system"))
            
    return current_content


def run_workflow(nodes: List[Dict], edges: List[Dict]) -> Dict[str, Any]:
    """
    Executes a DAG of workflow nodes.
    Returns structured chat_logs with speaker/message/type dicts.
    """
    chat_logs = []
    chat_logs.append(make_msg("🔧 System", "เริ่มต้นการรัน Workflow Pipeline", "system"))
    
    adj = {node['id']: [] for node in nodes}
    in_degree = {node['id']: 0 for node in nodes}
    node_map = {node['id']: node for node in nodes}
    
    for edge in edges:
        source = edge['source']
        target = edge['target']
        if source in adj and target in in_degree:
            adj[source].append(target)
            in_degree[target] += 1
            
    queue = [n_id for n_id, deg in in_degree.items() if deg == 0]
    
    outputs = {}
    final_output = ""
    
    while queue:
        current_id = queue.pop(0)
        node = node_map[current_id]
        node_type = node.get('type')
        data = node.get('data', {})
        
        display_name = agent_name(data.get("agent_type", node_type))
        chat_logs.append(make_msg("🔧 System", f"▶ กำลังประมวลผลโหนด: **{display_name}**", "system"))
        
        incoming_edges = [e for e in edges if e['target'] == current_id]
        input_texts = [outputs.get(e['source'], "") for e in incoming_edges if e['source'] in outputs]
        combined_input = "\n\n".join(input_texts) if input_texts else data.get("text", data.get("input_text", ""))
        
        try:
            if node_type == "input":
                outputs[current_id] = data.get("text", "")
                chat_logs.append(make_msg("📥 Input", data.get("text", "(ว่าง)"), "speak"))
                
            elif node_type == "agent":
                agent_type = data.get("agent_type")
                name = agent_name(agent_type)
                chat_logs.append(make_msg(name, "⏳ กำลังทำงาน...", "info"))
                result = execute_agent(agent_type, combined_input, data)
                outputs[current_id] = result
                preview = result[:500] + ("..." if len(result) > 500 else "")
                chat_logs.append(make_msg(name, preview, "speak"))
                
            elif node_type == "debate":
                generator = data.get("generator")
                critic = data.get("critic")
                result = execute_debate_loop(generator, critic, combined_input, data, chat_logs)
                outputs[current_id] = result
                
            elif node_type == "output":
                outputs[current_id] = combined_input
                final_output = combined_input
                preview = combined_input[:500] + ("..." if len(combined_input) > 500 else "")
                chat_logs.append(make_msg("📤 Output", preview, "speak"))
                
        except Exception as e:
            err_msg = f"เกิดข้อผิดพลาดที่โหนด {current_id}: {str(e)}"
            logger.error(err_msg, exc_info=True)
            chat_logs.append(make_msg("🔧 System", err_msg, "error"))
            break
            
        for child_id in adj[current_id]:
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)
                
    chat_logs.append(make_msg("🔧 System", "✅ Workflow ทำงานเสร็จสิ้น", "system"))
    return {
        "final_output": final_output,
        "chat_logs": chat_logs,
        "node_outputs": outputs
    }
