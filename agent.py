import json
import operator
import os
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig  # Thêm import
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from tools import (
    get_company_info,
    get_market_sentiment,
    get_stock_data,
)


class TechnicalAnalysis(BaseModel):
    indicator: str = Field(description="Tên chỉ số (SMA, RSI...)")
    value: float = Field(description="Giá trị của chỉ số")
    window_size: int = Field(description="Chu kỳ tính toán")


class StockPriceRow(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class FinancialResponse(BaseModel):
    """Cấu trúc phản hồi cuối cùng cho người dùng"""

    summary: str = Field(description="Tóm tắt ngắn gọn câu trả lời")
    company_profile: Optional[List[Dict[str, Any]]] = None
    historical_data: Optional[List[StockPriceRow]] = None
    technical_indicators: Optional[List[TechnicalAnalysis]] = None
    download_url: Optional[str] = None


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]


load_dotenv()
api_key = os.getenv("GOOGLE_API")
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, api_key=api_key)
tools = [get_stock_data, get_company_info, get_market_sentiment]
llm_with_tools = llm.bind_tools(tools)
structured_llm = llm.with_structured_output(FinancialResponse)


def call_gemini(state: AgentState):
    current_date = datetime.now().strftime("%d/%m/%Y")
    system_instruction = SystemMessage(
        content=(
            f"Hôm nay là {current_date}. Bạn là Giám đốc phân tích đầu tư. "
            "Nhiệm vụ của bạn là tổng hợp dữ liệu để đưa ra lời khuyên theo khung sau:\n"
            "1. Kỹ thuật: Nếu RSI < 30 là quá bán (Cơ hội), RSI > 70 là quá mua (Rủi ro). "
            "Nếu giá nằm trên SMA là xu hướng tăng.\n"
            "2. Tâm lý: Đối chiếu sentiment từ tin tức. Nếu điểm tâm lý đồng thuận với kỹ thuật, độ tin cậy cao hơn.\n"
            "3. Cơ bản: Xem xét ban lãnh đạo và hồ sơ công ty để đánh giá uy tín dài hạn.\n"
            "Luôn đưa ra cảnh báo rằng đây chỉ là thông tin tham khảo, không phải lời khuyên tài chính pháp lý."
        )
    )
    messages = [system_instruction] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def execute_tool_calls(state: AgentState, config: RunnableConfig):
    last_msg = state["messages"][-1]
    tool_outputs = []
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return {"messages": []}
    for tool_call in last_msg.tool_calls:
        selected_tool = {
            "get_stock_data": get_stock_data,
            "get_company_info": get_company_info,
            "get_market_sentiment": get_market_sentiment,
        }[tool_call["name"]]

        output = selected_tool.invoke(tool_call["args"], config=config)
        tool_outputs.append(
            ToolMessage(tool_call_id=tool_call["id"], content=str(output))
        )

    return {"messages": tool_outputs}


def format_output(state: AgentState):
    messages = state["messages"]
    response = structured_llm.invoke(messages)

    if hasattr(response, "model_dump"):
        data_dict = response.model_dump()
    elif isinstance(response, dict):
        data_dict = response
    else:
        data_dict = {"summary": str(response)}

    json_content = json.dumps(data_dict)

    return {"messages": [AIMessage(content=json_content)]}


def route_after_brain(state):
    if state["messages"][-1].tool_calls:
        return "tool_hands"
    return "summarizer"


workflow = StateGraph(AgentState)
workflow.add_node("gemini_brain", call_gemini)
workflow.add_node("tool_hands", execute_tool_calls)
workflow.add_node("summarizer", format_output)  # Node mới
workflow.set_entry_point("gemini_brain")
workflow.add_conditional_edges("gemini_brain", route_after_brain)
workflow.add_edge("tool_hands", "gemini_brain")
workflow.add_edge("summarizer", END)

app = workflow.compile()
