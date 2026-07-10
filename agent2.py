import os
import requests
from typing import TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

# ==========================================
# 1. 환경 변수 로드
# ==========================================
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")

if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY가 설정되어 있지 않습니다.")
if not NEWSDATA_API_KEY:
    print("Warning: NEWSDATA_API_KEY가 설정되어 있지 않습니다. 뉴스 검색이 제한될 수 있습니다.")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ==========================================
# 2. State 정의 (PlannerState)
# ==========================================
class PlannerState(TypedDict):
    user_input: str
    subject: str
    exam_date: str
    study_hours: int
    next_agent: str
    plan_result: str
    news_result: str
    progress_result: str
    final_answer: str

# ==========================================
# 3. 노드 함수 정의 (수퍼바이저 + 3개의 에이전트)
# ==========================================
def supervisor_node(state: PlannerState):
    """사용자의 요청을 분석하여 적절한 에이전트 배정"""
    system_prompt = (
        "당신은 AI 학습 플래너 시스템의 수퍼바이저입니다.\n"
        "사용자의 질문이나 요청을 분석하여 다음 세 가지 에이전트 중 하나를 선택하세요.\n"
        "반드시 'plan', 'news', 'progress' 중 하나의 단어만 출력하세요.\n\n"
        "- 학습 계획을 세워달라고 하거나, 시험 대비 일정/전략을 물어보면: plan\n"
        "- 과목과 관련된 최신 뉴스, 동향, 학습 자료 검색을 요청하면: news\n"
        "- 오늘 공부한 내용을 보고하거나 진도에 대한 피드백/질문을 원하면: progress"
    )
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["user_input"])
    ])
    
    next_agent = response.content.strip().lower()
    if next_agent not in ["plan", "news", "progress"]:
        next_agent = "plan" # 기본값
        
    return {"next_agent": next_agent}

import datetime

def plan_agent_node(state: PlannerState):
    """목표 과목들, 날짜, 학습 시간을 바탕으로 계획 생성"""
    today = datetime.date.today()
    try:
        exam = datetime.datetime.strptime(state['exam_date'], "%Y-%m-%d").date()
        days_left = (exam - today).days
    except ValueError:
        days_left = 0
        
    # 남은 일수가 음수면 0으로 처리
    days_left = max(0, days_left)
    total_hours = days_left * state['study_hours']
    
    prompt = (
        f"현재 날짜: {today.strftime('%Y-%m-%d')}\n"
        f"시험 날짜: {state['exam_date']}\n"
        f"남은 기간: 총 {days_left}일\n"
        f"하루 학습 가능 시간: {state['study_hours']}시간\n"
        f"총 확보된 학습 가능 시간: 약 {total_hours}시간\n"
        f"목표 과목(들): {state['subject']}\n\n"
        f"[매우 중요] 당신은 위에서 계산된 남은 기간({days_left}일)과 총 학습 시간({total_hours}시간)을 '절대' 임의로 바꾸거나 잘못 계산해서는 안 됩니다. "
        f"반드시 남은 {days_left}일에 맞추어 현실적인 시간 분배 전략과 구체적인 일별/주차별 학습 계획을 세워주세요.\n\n"
        f"사용자 요청: '{state['user_input']}'"
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"plan_result": response.content}

def news_agent_node(state: PlannerState):
    """NewsData API를 활용한 관련 자료 검색"""
    # 여러 과목이 쉼표로 구분되어 있을 경우를 대비해 첫 번째 과목만 주로 검색하거나 띄어쓰기로 변환
    query_subject = state["subject"].replace(",", " ").split()[0] if state["subject"] else ""
    news_text = "관련 최신 뉴스를 찾을 수 없습니다."
    
    # NewsData API 호출
    if NEWSDATA_API_KEY and query_subject:
        try:
            url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q={query_subject}&language=ko"
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                results = data.get("results", [])
                if results:
                    articles = []
                    # 상위 3개 뉴스 추출
                    for i, article in enumerate(results[:3]):
                        articles.append(f"{i+1}. {article.get('title')} ({article.get('link')})")
                    news_text = "\n".join(articles)
        except Exception as e:
            news_text = f"뉴스 검색 중 통신 오류가 발생했습니다: {e}"
            
    prompt = (
        f"목표 과목 '{state['subject']}'에 대한 최신 뉴스 및 동향 검색 결과입니다:\n{news_text}\n\n"
        f"이 정보들을 요약하고 사용자의 질문('{state['user_input']}')에 맞게 유용한 학습 정보로 부드럽게 가공해주세요."
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"news_result": response.content}

def progress_agent_node(state: PlannerState):
    """오늘의 진도 체크 및 피드백 제공"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    prompt = (
        f"오늘 날짜: {today}\n"
        f"목표 과목(들): {state['subject']}\n"
        f"오늘 학습한 내용 및 사용자 요청: '{state['user_input']}'\n\n"
        "이 내용을 바탕으로 오늘의 학습 진도와 노력을 칭찬하고, 부족한 부분에 대한 피드백과 내일 학습을 위한 조언을 작성해주세요."
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"progress_result": response.content}

def final_node(state: PlannerState):
    """최종 결과 취합 및 응답 생성"""
    agent_info = ""
    if state.get("plan_result"): 
        agent_info = f"[학습 계획 결과]\n{state['plan_result']}"
    elif state.get("news_result"): 
        agent_info = f"[최신 자료 검색 결과]\n{state['news_result']}"
    elif state.get("progress_result"): 
        agent_info = f"[진도 피드백 결과]\n{state['progress_result']}"
    
    prompt = (
        "당신은 따뜻하고 전문적인 AI 학습 플래너입니다.\n"
        "아래 제공된 [에이전트 분석 결과]를 바탕으로 사용자에게 제공할 최종 응답을 다듬어 작성해주세요.\n"
        "사용자가 친근감을 느낄 수 있도록 이모지도 활용하고 응원과 격려를 꼭 포함해주세요.\n\n"
        f"{agent_info}"
    )
    
    response = llm.invoke([SystemMessage(content=prompt)])
    return {"final_answer": response.content}

# ==========================================
# 4. 조건 분기 및 StateGraph 구성
# ==========================================
def route_agent(state: PlannerState):
    mapping = {
        "plan": "plan_agent_node",
        "news": "news_agent_node",
        "progress": "progress_agent_node"
    }
    return mapping.get(state["next_agent"], "plan_agent_node")

workflow = StateGraph(PlannerState)
workflow.add_node("supervisor_node", supervisor_node)
workflow.add_node("plan_agent_node", plan_agent_node)
workflow.add_node("news_agent_node", news_agent_node)
workflow.add_node("progress_agent_node", progress_agent_node)
workflow.add_node("final_node", final_node)

workflow.add_edge(START, "supervisor_node")
workflow.add_conditional_edges("supervisor_node", route_agent, {
    "plan_agent_node": "plan_agent_node",
    "news_agent_node": "news_agent_node",
    "progress_agent_node": "progress_agent_node"
})
workflow.add_edge("plan_agent_node", "final_node")
workflow.add_edge("news_agent_node", "final_node")
workflow.add_edge("progress_agent_node", "final_node")
workflow.add_edge("final_node", END)

app_graph = workflow.compile()

# ==========================================
# 5. 외부 호출용 함수
# ==========================================
def run_planner(user_input: str, subject: str, exam_date: str, study_hours: int) -> str:
    initial_state = {
        "user_input": user_input,
        "subject": subject,
        "exam_date": exam_date,
        "study_hours": study_hours,
        "next_agent": "",
        "plan_result": "",
        "news_result": "",
        "progress_result": "",
        "final_answer": ""
    }
    result = app_graph.invoke(initial_state)
    return result["final_answer"]
