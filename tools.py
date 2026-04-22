from vnstock import Quote,Company
import pandas_ta as ta
import pandas as pd
import json
from langchain_core.tools import tool

@tool
def get_stock_data(ticker: str, days:  str = '100', interval: str = 'd', windows: int = 20):
    """Truy xuất dữ liệu giá lịch sử từ vnstock"""
    quote = Quote(symbol=ticker, source='KBS')
    df = quote.history(length=days, interval=interval)
    df.ta.sma(length=windows, append=True)
    df.ta.rsi(length=windows, append=True)
    # latest = df.iloc[-1]
    result = {
        "ticker": ticker,
        "open":df['open'].iloc[0],
        "highest": df['high'].max(),
        "lowest": df['low'].min(),
        "avg_volumn": df['volume'].mean(),
        "close": df['close'].iloc[-1],
        "SMA": df[f'SMA_{windows}'].iloc[-1],
        "RSI": df[f'RSI_{windows}'].iloc[-1]
    }
    # result = df.to_dict(orient='records')
    return result

@tool
def get_company_info(ticker: str, category: str, filter_by: str = 'working'):
    """Truy xuất thông tin công ty từ vnstock
    Args:
        ticker: Mã chứng khoán (ví dụ: 'FPT', 'HPG').
        category: Hạng mục thông tin bao gồm:
            - 'profile': Tổng quan công ty
            - 'ownership': Tỷ lệ sở hữu
            - 'shareholders': Danh sách cổ đông
            - 'subsidiaries': Công ty con
            - 'leadership': Ban lãnh đạo/Danh sách cán bộ
            - 'news': Tin tức doanh nghiệp
        filter_by: Chỉ dùng khi category='leadership'.
            - 'working': Lãnh đạo đang đương nhiệm (mặc định).
            - 'resigned': Lãnh đạo đã nghỉ việc.
            - 'all': Tất cả lịch sử lãnh đạo.
    """
    company = Company(symbol=ticker, source='KBS')
    data_map = {
        "profile": company.overview,
        "ownership": company.ownership,
        "shareholders": company.shareholders,
        "subsidiaries": company.subsidiaries,
        "leadership": company.officers,
        "news": company.news,
        # "earnings": company.earnings(),
        # "financials": company.financials(),
    }
    try:
        data_func = data_map.get(category)
        if not data_func:
            return f"Hạng mục {category} không được hỗ trợ."

        if category == "leadership":
            df = data_func(filter_by=filter_by)
        else:
            df = data_func()
        result = df.to_dict(orient='records')
        return result[:3] # Giới hạn số lượng bản ghi
    except Exception as e:
        return f"Lỗi khi truy xuất dữ liệu: {str(e)}"
