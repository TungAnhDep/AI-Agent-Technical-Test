from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from agent import app as agent_workflow

app = FastAPI(title="Financial AI Agent API", version="1.0")
app.mount("/download", StaticFiles(directory="exports"), name="download")
# Cấu trúc dữ liệu đầu vào cho API
class ChatRequest(BaseModel):
    query: str

# Cấu trúc dữ liệu trả về
class ChatResponse(BaseModel):
    query: str
    response: str
    steps: List[dict]

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        steps_log = []
        final_answer = ""
        
        async for event in agent_workflow.astream(
            {"messages": [HumanMessage(content=request.query)]}
        ):
            for node, value in event.items():
                last_msg = value["messages"][-1]
                
                step_info = {"node": node}
                
                if node == "gemini_brain":
                    if last_msg.tool_calls:
                        step_info["action"] = f"Gọi hàm: {last_msg.tool_calls[0]['name']}"
                    else:
                        final_answer = last_msg.content
                        step_info["action"] = "Trả lời cuối cùng"
                elif node == "tool_hands":
                    step_info["action"] = "Đã lấy dữ liệu từ hệ thống"
                
                steps_log.append(step_info)

        return ChatResponse(
            query=request.query,
            response=final_answer,
            steps=steps_log
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "running", "agent": "Financial Agent v1"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)