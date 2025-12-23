import os
import json
import time
from openai import OpenAI

# ==========================================
# 1. 逻辑定义 (Old vs New)
# ==========================================

def old_wrap_thinking_by_reasoning_content(delta_dict: dict, is_reasoning: bool) -> tuple[str, bool]:
    """[OLD] PR 修改前的逻辑"""
    content = delta_dict.get("content") or ""
    reasoning_content = delta_dict.get("reasoning_content")
    output = content
    
    if reasoning_content:
        if not is_reasoning:
            output = "<think>\n" + reasoning_content
            is_reasoning = True
        else:
            output = reasoning_content
    else:
        # 旧逻辑缺陷
        if is_reasoning and content:
            output = "\n</think>" + content
            is_reasoning = False
            
    return output, is_reasoning

def new_wrap_thinking_by_reasoning_content(delta_dict: dict, is_reasoning: bool) -> tuple[str, bool]:
    """[NEW] PR 修改后的逻辑"""
    content = delta_dict.get("content") or ""
    reasoning_content = delta_dict.get("reasoning_content")
    output = content
    
    if reasoning_content:
        if not is_reasoning:
            output = "<think>\n" + reasoning_content
            is_reasoning = True
        else:
            output = reasoning_content
    else:
        # 新逻辑
        if is_reasoning:
            is_reasoning = False
            if not reasoning_content:
                output = "\n</think>"
            if content:
                output += content
                
    return output, is_reasoning

def get_reasoning_from_chunk(delta) -> str | None:
    val = getattr(delta, "reasoning_content", None)
    if val is not None: return val
    if hasattr(delta, "model_extra") and delta.model_extra:
        return delta.model_extra.get("reasoning_content")
    if hasattr(delta, "__dict__"):
         return delta.__dict__.get("reasoning_content")
    return None

def mock_weather_tool(city: str):
    return json.dumps({"city": city, "weather": "Sunny", "temperature": "25°C", "humidity": "40%"})


def main():
    api_key = "your_api_key"
    base_url = "your_base_url"
    model = "your_model"
    client = OpenAI(api_key=api_key, base_url=base_url)

    
    # --- Round 1 ---
    msgs = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "北京天气如何？"}]
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]
    
    print("\n[Request 1] ...")
    r1_deltas = []
    r1_reasoning = ""
    tool_calls = []
    
    try:
        for chunk in client.chat.completions.create(model=model, messages=msgs, tools=tools, stream=True,extra_body={"thinking": {"type": "enabled"}}):
            if not chunk.choices: continue
            d = chunk.choices[0].delta
            r1_deltas.append(d)
            
            rc = get_reasoning_from_chunk(d)
            if rc: r1_reasoning += rc
            if d.tool_calls:
                for tc in d.tool_calls:
                    if len(tool_calls) <= tc.index:
                        tool_calls.append({"id": tc.id, "function": {"name": tc.function.name, "arguments": ""}})
                    tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
    except Exception as e:
        print(e); return
    
    print(f"R1 Done. Tool Calls: {len(tool_calls)}")
    
    # --- Tool Exec ---
    msgs.append({"role": "assistant", "tool_calls": [{"id": t["id"], "type": "function", "function": t["function"]} for t in tool_calls], "reasoning_content": r1_reasoning})
    for t in tool_calls:
        msgs.append({"role": "tool", "tool_call_id": t["id"], "content": mock_weather_tool("Beijing")})
        
    # --- Round 2 ---
    print("\n[Request 2] ...")
    r2_deltas = []
    try:
        for chunk in client.chat.completions.create(model=model, messages=msgs, tools=tools, stream=True,extra_body={"thinking": {"type": "enabled"}}):
            if not chunk.choices: continue
            r2_deltas.append(chunk.choices[0].delta)
    except Exception as e:
        print(e); return
        
    print("R2 Done.")
    
    # --- Contrast ---
    print("\n" + "="*80)
    print("OUTPUT VISUALIZATION")
    print("="*80)
    
    for label, proc_func in [("OLD_LOGIC", old_wrap_thinking_by_reasoning_content), ("NEW_LOGIC", new_wrap_thinking_by_reasoning_content)]:
        print(f"\n>>> Mode: {label} <<<")
        
        # Simulate Dify Internal: Reset is_reasoning per Invoke
        
        # 1. Generate R1 Output
        is_reasoning = False
        r1_text = ""
        for d in r1_deltas:
            # Reconstruct dict
            dct = {"content": d.content, "reasoning_content": get_reasoning_from_chunk(d)}
            out, is_reasoning = proc_func(dct, is_reasoning)
            r1_text += out
            
        # 2. Generate R2 Output
        is_reasoning = False # Reset for new request
        r2_text = ""
        for d in r2_deltas:
            dct = {"content": d.content, "reasoning_content": get_reasoning_from_chunk(d)}
            out, is_reasoning = proc_func(dct, is_reasoning)
            r2_text += out
            
        # Final Visual Check
        print(f"\n--- Human Readability ({label}) ---")
        print(f"AI: {r1_text}")
        print(f"[System: Tool Result used...]")
        print(f"AI: {r2_text}")
        print("\n" + "="*80)

if __name__ == "__main__":
    main()
