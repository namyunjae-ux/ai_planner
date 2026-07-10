import streamlit as st
import datetime
from agent2 import run_planner

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="AI 학습 플래너", page_icon="🎓", layout="wide")
st.title("🎓 AI 학습 플래너 서비스")

# ==========================================
# 2. Session State 초기화 (대화 기록 유지)
# ==========================================
if "planner_messages" not in st.session_state:
    st.session_state.planner_messages = [
        {"role": "assistant", "content": "안녕하세요! 목표 달성을 도와드릴 AI 학습 플래너입니다. 좌측에 시험 일정을 설정하시고, 언제든 학습 계획이나 진도 피드백을 요청하세요!"}
    ]

# ==========================================
# 3. 사이드바 (과목 정보 및 상태 표시)
# ==========================================
with st.sidebar:
    st.header("📅 나의 학습 목표")
    
    # 목표 입력 영역
    subject = st.text_input("목표 과목들 (쉼표로 구분하여 여러 개 입력 가능)", value="소프트웨어공학, 데이터베이스", placeholder="예: 국어, 영어, 수학")
    exam_date = st.date_input("시험 날짜", min_value=datetime.date.today())
    study_hours = st.slider("하루 학습 가능 시간 (시간)", min_value=1, max_value=24, value=4)
    
    # D-Day 계산 로직
    today = datetime.date.today()
    d_day = (exam_date - today).days
    
    st.divider()
    
    # 남은 날짜 시각화
    if d_day > 0:
        st.metric(label="시험까지 남은 시간", value=f"D-{d_day}")
    elif d_day == 0:
        st.metric(label="시험까지 남은 시간", value="D-DAY! 화이팅!")
    else:
        st.metric(label="시험까지 남은 시간", value="시험 종료됨")
        
    st.divider()
    
    # 초기화 버튼
    if st.button("🗑️ 대화 기록 초기화", use_container_width=True):
        st.session_state.planner_messages = [
            {"role": "assistant", "content": "안녕하세요! 목표 달성을 도와드릴 AI 학습 플래너입니다. 좌측에 시험 일정을 설정하시고, 언제든 학습 계획이나 진도 피드백을 요청하세요!"}
        ]
        st.rerun()

# ==========================================
# 4. 메인 화면 채팅 UI 렌더링
# ==========================================
for msg in st.session_state.planner_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ==========================================
# 5. 사용자 채팅 입력창
# ==========================================
if user_input := st.chat_input("공부 내용이나 궁금한 점을 자유롭게 입력해주세요!"):
    # 사용자 메시지 화면 출력 및 저장
    st.session_state.planner_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
        
    # AI 응답 처리
    with st.chat_message("assistant"):
        with st.spinner("AI 플래너가 최적의 솔루션을 고민 중입니다..."):
            # agent2.py의 run_planner 함수 호출
            response = run_planner(
                user_input=user_input, 
                subject=subject, 
                exam_date=exam_date.strftime("%Y-%m-%d"), 
                study_hours=study_hours
            )
            st.write(response)
            
    # AI 응답 저장
    st.session_state.planner_messages.append({"role": "assistant", "content": response})
