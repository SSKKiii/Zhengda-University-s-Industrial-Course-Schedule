import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import os

# --- 页面全局配置 ---
st.set_page_config(page_title="实时智能课表", page_icon="🏫", layout="wide")

# --- 1. 核心时间与映射逻辑 ---
tz = pytz.timezone('Asia/Taipei')
now = datetime.now(tz)

# 锚点：2026年5月28日 是 第13周 周四，推算第1周周一为 2026年3月2日
TERM_START_DATE = date(2026, 3, 2)
days_since_start = (now.date() - TERM_START_DATE).days
real_week = (days_since_start // 7) + 1
real_weekday = now.weekday()  # 0=周一, 6=周日
real_hour = now.hour
real_period = "上午" if real_hour < 12 else "下午"
real_week = max(1, min(real_week, 18))

weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}

# 精确时间映射字典
time_mapping = {
    "1-2": {"时段": "上午", "时间": "08:00-08:45, 08:55-09:40"},
    "3-4": {"时段": "上午", "时间": "10:10-10:55, 11:05-11:50"},
    "5-6": {"时段": "下午", "时间": "14:00-14:45, 14:55-15:40"},
    "7-8": {"时段": "下午", "时间": "16:00-16:45, 17:05-17:40"},
    "9-10": {"时段": "下午", "时间": "19:00-19:45, 19:45-20:30"}
}

# --- 2. Excel数据解析模块 ---
@st.cache_data
def load_and_parse_excel():
    parsed_schedule = {}
    filename = "课表.xlsx"
    
    if not os.path.exists(filename):
        st.error(f"未找到数据文件：{filename}。请确保已将其上传至当前目录。")
        return parsed_schedule

    try:
        xls = pd.ExcelFile(filename)
        # 遍历工作表，以索引位置代表周次 (索引0 = 第1周)
        for i, sheet_name in enumerate(xls.sheet_names):
            week_num = i + 1
            if week_num > 18:
                break
                
            raw_df = pd.read_excel(xls, sheet_name=sheet_name)
            flat_rows = []
            
            for weekday_idx, weekday_name in weekday_map.items():
                # 定位对应的列
                actual_col_name = None
                for col in raw_df.columns:
                    if weekday_name in str(col) or weekday_name[2:] in str(col):
                        actual_col_name = col
                        break
                
                if not actual_col_name:
                    continue
                    
                # 逐行解析
                for row_idx, cell_value in enumerate(raw_df[actual_col_name]):
                    # 获取第一列的节次标签
                    time_label = str(raw_df.iloc[row_idx, 0]).strip()
                    
                    if pd.isna(cell_value) or str(cell_value).strip() in ["", "nan", "无", "-"]:
                        continue
                        
                    # 匹配具体的节次键值
                    matched_key = None
                    for key in time_mapping.keys():
                        if key in time_label:
                            matched_key = key
                            break
                            
                    if matched_key:
                        period = time_mapping[matched_key]["时段"]
                        exact_time = time_mapping[matched_key]["时间"]
                    else:
                        continue # 过滤非标准节次行
                        
                    # 弹性解析单元格内容
                    lines = [line.strip() for line in str(cell_value).split('\n') if line.strip()]
                    
                    if len(lines) == 2:
                        course = lines[0]
                        teacher = "-"
                        room = lines[1]
                    elif len(lines) >= 3:
                        course = lines[0]
                        teacher = lines[1]
                        room = lines[2]
                    else:
                        course = lines[0] if lines else "未知课程"
                        teacher = "-"
                        room = "-"
                        
                    flat_rows.append({
                        "星期": weekday_name,
                        "时段": period,
                        "节次": matched_key,
                        "精确时间": exact_time,
                        "课程": course,
                        "老师": teacher,
                        "教室": room
                    })
                    
            parsed_schedule[week_num] = pd.DataFrame(flat_rows)
            
    except Exception as e:
        st.error(f"解析 Excel 失败: {e}")
        
    return parsed_schedule

all_weeks_data = load_and_parse_excel()

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

# --- 4. 主界面视图渲染 ---
st.title("🏫 智能实时课表")

is_current_day = (selected_week == real_week) and (selected_weekday_idx == real_weekday)

if is_current_day:
    st.success(f"🟢 **实时状态追踪中**：当前是 **第{real_week}周 {weekday_map[real_weekday]}** (系统时间: {now.strftime('%H:%M')})")
else:
    st.info(f"⚪ **浏览模式**：正在查看 **第{selected_week}周 {selected_weekday_name}** 的课表（当前实际为第{real_week}周）")

st.divider()

current_week_df = all_weeks_data.get(selected_week, pd.DataFrame())

if not current_week_df.empty:
    day_df = current_week_df[current_week_df['星期'] == selected_weekday_name]
else:
    day_df = pd.DataFrame()

col1, col2 = st.columns(2)

with col1:
    st.subheader("☀️ 上午时段")
    if not day_df.empty:
        morning_df = day_df[day_df['时段'] == '上午'].drop(columns=['星期', '时段'], errors='ignore')
    else:
        morning_df = pd.DataFrame()

    if not morning_df.empty:
        if is_current_day and real_period == "上午":
            st.markdown("🔥 **当前时段课程**")
        st.dataframe(morning_df, use_container_width=True, hide_index=True)
    else:
        st.write("🍵 上午无课")

with col2:
    st.subheader("🌙 下午与晚间时段")
    if not day_df.empty:
        afternoon_df = day_df[day_df['时段'] == '下午'].drop(columns=['星期', '时段'], errors='ignore')
    else:
        afternoon_df = pd.DataFrame()

    if not afternoon_df.empty:
        if is_current_day and real_period == "下午":
            st.markdown("🔥 **当前时段课程**")
        st.dataframe(afternoon_df, use_container_width=True, hide_index=True)
    else:
        st.write("🍵 下午无课")
