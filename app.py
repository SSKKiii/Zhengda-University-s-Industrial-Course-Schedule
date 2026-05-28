import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import os

# --- 页面全局配置 ---
st.set_page_config(page_title="郑州大学2026学年春季学期实时课表", page_icon="🏫", layout="wide")

# --- 1. 核心时间与映射逻辑 ---
tz = pytz.timezone('Asia/Taipei')
now = datetime.now(tz)

TERM_START_DATE = date(2026, 3, 2)
days_since_start = (now.date() - TERM_START_DATE).days
real_week = (days_since_start // 7) + 1
real_weekday = now.weekday()  # 0=周一, 6=周日
real_hour = now.hour
real_period = "上午" if real_hour < 12 else "下午"
real_week = max(1, min(real_week, 18))

weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
weekday_short = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}

chinese_nums = {
    1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九', 
    10: '十', 11: '十一', 12: '十二', 13: '十三', 14: '十四', 15: '十五', 16: '十六', 17: '十七', 18: '十八'
}

time_mapping = {
    "1-2": {"时段": "上午", "时间": "08:00-09:40"},
    "3-4": {"时段": "上午", "时间": "10:10-11:50"},
    "5-6": {"时段": "下午", "时间": "14:00-15:40"},
    "7-8": {"时段": "下午", "时间": "16:00-17:40"},
    "9-10": {"时段": "下午", "时间": "19:00-20:30"}
}

# --- 2. 增强型自适应编码 CSV 解析模块 ---
@st.cache_data
def load_and_parse_csvs():
    parsed_schedule = {}
    debug_info = {"files_found": [], "encoding_used": {}, "raw_data_preview": {}}
    
    for i in range(1, 19):
        possible_names = [
            f"课表.xlsx - 第{chinese_nums[i]}周.csv",
            f"课表.xlsx - 第{chinese_nums[i]}周 .csv",
            f"课表-第{i}周.xlsx - Sheet1.csv"
        ]
        
        filename = None
        for name in possible_names:
            if os.path.exists(name):
                filename = name
                break
                
        if not filename:
            parsed_schedule[i] = pd.DataFrame()
            continue
            
        debug_info["files_found"].append(filename)
        
        raw_df = None
        used_enc = None
        for enc in ['utf-8', 'gbk', 'gb18030', 'utf-8-sig']:
            try:
                raw_df = pd.read_csv(filename, header=None, encoding=enc)
                used_enc = enc
                break 
            except Exception:
                continue
                
        if raw_df is None or raw_df.empty:
            parsed_schedule[i] = pd.DataFrame()
            continue
            
        debug_info["encoding_used"][filename] = used_enc
        
        if i == real_week:
            debug_info["raw_data_preview"] = raw_df.head(10).astype(str).to_dict()

        try:
            # 🎯 核心修复点：极其严格的表头定位机制
            header_row_idx = 0
            for idx, row in raw_df.iterrows():
                row_str = "".join([str(x) for x in row.values if pd.notna(x)])
                # 只有当一行同时出现“周一”和“周二”（或星期一、二）时，才认定为真正的表头，忽略大标题
                if ("周一" in row_str or "星期一" in row_str) and ("周二" in row_str or "星期二" in row_str):
                    header_row_idx = idx
                    break
                    
            df_cleaned = pd.read_csv(filename, skiprows=header_row_idx, encoding=used_enc)
            
            flat_rows = []
            for weekday_idx, weekday_name in weekday_map.items():
                short_name = weekday_short[weekday_idx]
                
                actual_col_name = None
                for col in df_cleaned.columns:
                    col_str = str(col).strip()
                    if weekday_name in col_str or short_name in col_str or (len(col_str) == 1 and col_str == weekday_name[-1]):
                        actual_col_name = col
                        break
                
                if not actual_col_name:
                    continue
                    
                for row_idx, cell_value in enumerate(df_cleaned[actual_col_name]):
                    time_label = str(df_cleaned.iloc[row_idx, 0]).strip()
                    
                    if pd.isna(cell_value) or str(cell_value).strip() in ["", "nan", "无", "-", "None"]:
                        continue
                        
                    matched_key = None
                    for key in time_mapping.keys():
                        if key in time_label or key.replace("-", "~") in time_label:
                            matched_key = key
                            break
                            
                    if matched_key:
                        period = time_mapping[matched_key]["时段"]
                        exact_time = time_mapping[matched_key]["时间"]
                    else:
                        if any(char in time_label for char in ["1", "2", "3", "4", "上午"]) or row_idx < 3:
                            period = "上午"
                        else:
                            period = "下午"
                        matched_key = time_label
                        exact_time = "时段参考: " + time_label
                        
                    lines = [line.strip() for line in str(cell_value).split('\n') if line.strip()]
                    
                    if len(lines) == 1:
                        course, room, remarks = lines[0], "-", "-"
                    elif len(lines) == 2:
                        course, room, remarks = lines[0], lines[1], "-"
                    elif len(lines) >= 3:
                        course, room, remarks = lines[0], lines[1], lines[2]
                    else:
                        continue
                        
                    flat_rows.append({
                        "星期": weekday_name,
                        "时段": period,
                        "节次": matched_key,
                        "具体时间": exact_time,
                        "课程": course,
                        "教师与教室": room,
                        "周次/备注": remarks
                    })
                    
            parsed_schedule[i] = pd.DataFrame(flat_rows)
            
        except Exception as e:
            debug_info[f"parsing_error_week_{i}"] = str(e)
            parsed_schedule[i] = pd.DataFrame()
            
    return parsed_schedule, debug_info

# 执行加载
all_weeks_data, debug_log = load_and_parse_csvs()

# --- 3. 侧边栏交互控制 ---
st.sidebar.title("⚙️ 课表控制台")

selected_week = st.sidebar.selectbox(
    "切换周次", 
    options=list(range(1, 19)), 
    index=real_week - 1,
    format_func=lambda x: f"第 {x} 周"
)

selected_weekday_name = st.sidebar.selectbox(
    "切换星期", 
    options=list(weekday_map.values()), 
    index=real_weekday
)

selected_weekday_idx = [k for k, v in weekday_map.items() if v == selected_weekday_name][0]

# --- 4. 主界面视图渲染 (上下排布) ---
st.title("🏫 智能实时课表")

is_current_day = (selected_week == real_week) and (selected_weekday_idx == real_weekday)

if is_current_day:
    st.success(f"🟢 **实时状态追踪中**：当前是 **第{real_week}周 {weekday_map[real_weekday]}** (系统时间: {now.strftime('%H:%M')})")
else:
    st.info(f"⚪ **浏览模式**：正在查看 **第{selected_week}周 {selected_weekday_name}** 的课表（当前实际为第{real_week}周）")

st.divider()

current_week_df = all_weeks_data.get(selected_week, pd.DataFrame())
day_df = current_week_df[current_week_df['星期'] == selected_weekday_name] if not current_week_df.empty else pd.DataFrame()

# 上午视图区
st.subheader("☀️ 上午时段")
morning_df = day_df[day_df['时段'] == '上午'].drop(columns=['星期', '时段'], errors='ignore') if not day_df.empty else pd.DataFrame()

if not morning_df.empty:
    if is_current_day and real_period == "上午":
        st.markdown("🔥 **当前进行中**")
    st.dataframe(morning_df, use_container_width=True, hide_index=True)
else:
    st.write("🍵 上午无课")

st.write("")

# 下午视图区
st.subheader("🌙 下午与晚间时段")
afternoon_df = day_df[day_df['时段'] == '下午'].drop(columns=['星期', '时段'], errors='ignore') if not day_df.empty else pd.DataFrame()

if not afternoon_df.empty:
    if is_current_day and real_period == "下午":
        st.markdown("🔥 **当前进行中**")
    st.dataframe(afternoon_df, use_container_width=True, hide_index=True)
else:
    st.write("🍵 下午无课")
