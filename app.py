import streamlit as st
import pandas as pd
import os
import time
import base64 # 이미지 처리를 위해 추가
import altair as alt  # 차트 라이브러리 추가
from datetime import datetime
from streamlit_quill import st_quill  # 텍스트 에디터

# --- 설정: 페이지 제목 ---
st.set_page_config(page_title="제조 현장 TPM 통합 시스템", layout="wide")

# --- 파일 및 폴더 경로 설정 ---
USER_FILE = 'users.csv'           # 회원 정보
SUGGESTION_FILE = 'suggestions.csv' # 제안제도 데이터
CIRCLE_FILE = 'circle_activity.csv' # 분임조 데이터
LEVEL_SETTINGS_FILE = 'level_settings.csv' # 레벨 기준 설정
UPLOAD_DIR = 'uploads'            # 파일 저장 폴더
HEADER_IMAGE = 'header_image.png'  # 로그인 화면 상단 이미지

# --- 초기화: 폴더 생성 ---
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- 함수: 데이터 로드/저장 ---
def load_csv(file_path, columns):
    if not os.path.exists(file_path):
        df = pd.DataFrame(columns=columns)
        df.to_csv(file_path, index=False)
        return df
    return pd.read_csv(file_path, dtype=str)

def save_csv(file_path, df):
    df.to_csv(file_path, index=False)

def save_uploaded_file(uploaded_file):
    if uploaded_file is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{uploaded_file.name}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return filename
    return ""

# --- 함수: 레벨 설정 로드 ---
def load_level_settings():
    if not os.path.exists(LEVEL_SETTINGS_FILE):
        data = {
            "이모지": ["🌱", "🥉", "🥈", "🥇", "👑"],
            "등급명": ["새싹", "브론즈", "실버", "골드", "마스터"],
            "필요점수": [0, 50, 200, 500, 1000]
        }
        df = pd.DataFrame(data)
        df.to_csv(LEVEL_SETTINGS_FILE, index=False)
        return df
    
    df = pd.read_csv(LEVEL_SETTINGS_FILE)
    # 기존 파일에 '이모지' 컬럼이 없으면 추가 (하위 호환성)
    if '이모지' not in df.columns:
        def get_emoji(name):
            val = str(name)
            if "새싹" in val: return "🌱"
            elif "브론즈" in val: return "🥉"
            elif "실버" in val: return "🥈"
            elif "골드" in val: return "🥇"
            elif "마스터" in val: return "👑"
            else: return "🔹"
        
        # '등급명' 컬럼이 있으면 그 앞에, 없으면 맨 앞에 추가
        loc_idx = df.columns.get_loc('등급명') if '등급명' in df.columns else 0
        df.insert(loc_idx, '이모지', df['등급명'].apply(get_emoji))
        
    return df

# --- 함수: 등급 이모지 제거 (평가 등급: S, A, B, C) ---
def add_grade_emoji(grade):
    if pd.isna(grade) or str(grade).strip() == "": return ""
    g_str = str(grade)
    
    # 구버전 데이터(골드 등)를 신버전(S~C)으로 매핑하여 표시
    if "골드" in g_str: return "S"
    if "실버" in g_str: return "A"
    if "브론즈" in g_str: return "B"
    if "참가상" in g_str: return "C"
    
    # 신버전 데이터 (이미 S, A, B, C인 경우 그대로 반환하거나, 이모지가 포함된 경우 제거)
    if "S" in g_str: return "S"
    if "A" in g_str: return "A"
    if "B" in g_str: return "B"
    if "C" in g_str: return "C"
    
    return g_str

# --- 함수: 사용자 레벨 계산 ---
def calculate_user_level(user_id, suggestions_df, level_df):
    if suggestions_df.empty:
        user_points = 0
    elif '포인트' in suggestions_df.columns:
        # 포인트 컬럼 숫자 변환 및 합계 (작성자ID 일치 & 채택 상태)
        valid_points = pd.to_numeric(
            suggestions_df.loc[
                (suggestions_df['작성자ID'] == user_id) & (suggestions_df['상태'] == '채택'), 
                '포인트'
            ], 
            errors='coerce'
        ).fillna(0)
        user_points = valid_points.sum()
    else:
        user_points = 0
        
    # 레벨 데이터 숫자 변환
    level_df['필요점수'] = pd.to_numeric(level_df['필요점수'], errors='coerce')
    level_df = level_df.sort_values('필요점수', ascending=True)
    
    current_level = "새싹" # 기본값
    next_level_name = "MAX"
    points_needed = 0
    next_level_total = user_points
    
    # 레벨 판별 (누적 점수 기준)
    # 점수가 높은 순이 아니라 낮은 순으로 정렬해서 순차적으로 확인하면, 마지막으로 만족하는 레벨이 현재 레벨임.
    # 하지만 여기서는 '다음 레벨'을 찾아야 하므로 낮은 순 정렬이 맞음.
    
    # 현재 달성한 가장 높은 레벨 찾기
    passed_levels = level_df[level_df['필요점수'] <= user_points]
    if not passed_levels.empty:
        row = passed_levels.iloc[-1]
        emoji = row['이모지'] if '이모지' in row else ""
        current_level = f"{emoji} {row['등급명']}"
        
    # 다음 레벨 찾기
    future_levels = level_df[level_df['필요점수'] > user_points]
    if not future_levels.empty:
        next_level_row = future_levels.iloc[0]
        next_level_name = next_level_row['등급명']
        next_level_total = next_level_row['필요점수']
        points_needed = next_level_total - user_points
    else:
        # 더 이상 레벨이 없는 경우
        next_level_name = "MAX"
        points_needed = 0
            
    return current_level, int(user_points), next_level_name, int(points_needed), int(next_level_total)

# --- 시스템 초기화: 관리자 계정 자동 생성 ---
def init_admin():
    users = load_csv(USER_FILE, ["사번", "비밀번호", "이름", "권한", "부서", "직책", "가입날짜"])
    if 'administrator' not in users['사번'].values:
        admin_data = {
            "사번": "administrator",
            "비밀번호": "admin07@",
            "이름": "시스템관리자",
            "권한": "Root",
            "부서": "관리팀",
            "직책": "관리자",
            "가입날짜": datetime.now().strftime("%y/%m/%d")
        }
        users = pd.concat([users, pd.DataFrame([admin_data])], ignore_index=True)
        save_csv(USER_FILE, users)

init_admin()

# --- 세션 상태 초기화 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = ""
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = ""
if 'user_name' not in st.session_state:
    st.session_state['user_name'] = ""
if 'delete_confirm_id' not in st.session_state:
    st.session_state['delete_confirm_id'] = None
if 'recall_confirm_id' not in st.session_state:
    st.session_state['recall_confirm_id'] = None
if 'admin_delete_confirm' not in st.session_state:
    st.session_state['admin_delete_confirm'] = False
if 'admin_delete_user_id' not in st.session_state:
    st.session_state['admin_delete_user_id'] = None
if 'admin_delete_indices' not in st.session_state:
    st.session_state['admin_delete_indices'] = []
if 'selected_users' not in st.session_state:
    st.session_state['selected_users'] = []

# ==========================================
# 1. 로그인 / 회원가입 / 비번변경 화면
# ==========================================
def login_page():
    # 로그인 화면 상단 이미지 표시
    if os.path.exists(HEADER_IMAGE):
        st.image(HEADER_IMAGE, use_container_width=True)
    elif os.path.exists('header_image.jpg'):
        st.image('header_image.jpg', use_container_width=True)
    elif os.path.exists('header_image.jpeg'):
        st.image('header_image.jpeg', use_container_width=True)
    
    st.title("🔐 TPM 활동 관리 시스템")
    
    tab1, tab2, tab3 = st.tabs(["로그인", "회원가입", "비밀번호 변경"])

    # [탭 1] 로그인
    with tab1:
        st.subheader("로그인")
        login_id = st.text_input("사번 (ID)", key="login_id")
        login_pw = st.text_input("비밀번호", type="password", key="login_pw")
        
        if st.button("로그인"):
            users = load_csv(USER_FILE, ["사번", "비밀번호", "이름", "권한", "부서", "직책", "가입날짜"])
            user = users[(users['사번'] == login_id) & (users['비밀번호'] == login_pw)]
            
            if not user.empty:
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = login_id
                st.session_state['user_name'] = user.iloc[0]['이름']
                st.session_state['user_role'] = user.iloc[0]['권한']
                st.success(f"{user.iloc[0]['이름']}님 환영합니다!")
                st.rerun()
            else:
                st.error("사번 또는 비밀번호가 일치하지 않습니다.")

    # [탭 2] 회원가입
    with tab2:
        st.subheader("신규 사용자 등록")
        with st.form("signup_form"):
            new_id = st.text_input("사번 (숫자)", placeholder="예: 120809")
            new_pw = st.text_input("비밀번호", type="password")
            new_pw_chk = st.text_input("비밀번호 확인", type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("이름")
                new_dept = st.text_input("부서")
            with col2:
                st.text_input("직무 구분", value="일반", disabled=True)
                new_rank = st.text_input("직급")
            
            submit_signup = st.form_submit_button("가입하기")
            
            if submit_signup:
                users = load_csv(USER_FILE, ["사번", "비밀번호", "이름", "권한", "부서", "직책", "가입날짜"])
                
                if new_id in users['사번'].values:
                    st.error("❌ 이미 가입된 사번(ID)입니다.")
                elif new_pw != new_pw_chk:
                    st.error("❌ 비밀번호가 서로 일치하지 않습니다.")
                elif not new_id or not new_pw or not new_name:
                    st.warning("필수 정보를 모두 입력해주세요.")
                else:
                    new_user = {
                        "사번": new_id, "비밀번호": new_pw, "이름": new_name,
                        "권한": "일반", "부서": new_dept, "직책": new_rank,
                        "가입날짜": datetime.now().strftime("%y/%m/%d")
                    }
                    users = pd.concat([users, pd.DataFrame([new_user])], ignore_index=True)
                    save_csv(USER_FILE, users)
                    st.success("✅ 가입 완료! 로그인해주세요.")

    # [탭 3] 비밀번호 변경
    with tab3:
        st.subheader("비밀번호 변경")
        chg_id = st.text_input("사번", key="chg_id")
        chg_old_pw = st.text_input("현재 비밀번호", type="password", key="chg_old")
        chg_new_pw = st.text_input("새 비밀번호", type="password", key="chg_new")
        chg_new_chk = st.text_input("새 비밀번호 확인", type="password", key="chg_chk")
        
        if st.button("비밀번호 변경"):
            users = load_csv(USER_FILE, ["사번", "비밀번호", "이름", "권한", "부서", "직책", "가입날짜"])
            user_idx = users.index[(users['사번'] == chg_id) & (users['비밀번호'] == chg_old_pw)].tolist()
            
            if not user_idx:
                st.error("정보가 일치하지 않습니다.")
            elif chg_new_pw != chg_new_chk:
                st.error("새 비밀번호가 일치하지 않습니다.")
            else:
                users.at[user_idx[0], '비밀번호'] = chg_new_pw
                save_csv(USER_FILE, users)
                st.success("✅ 비밀번호 변경 완료.")
    
    # 로그인 화면 하단 로고 이미지 (중심 정렬 - HTML/CSS 사용)
    st.markdown("<br>", unsafe_allow_html=True)  # 여백 추가
    if os.path.exists('logo_interojo.jpg'):
        with open('logo_interojo.jpg', "rb") as f:
            encoded_img = base64.b64encode(f.read()).decode()
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; width: 100%;">
                <img src="data:image/jpeg;base64,{encoded_img}" style="max-width: 200px; height: auto;">
            </div>
            """,
            unsafe_allow_html=True
        )

# ==========================================
# 2. 메인 애플리케이션
# ==========================================
def main_app():
    user_role = st.session_state['user_role']
    user_name = st.session_state['user_name']
    user_id = st.session_state['user_id']

    with st.sidebar:
        st.info(f"👤 **{user_name}** ({user_role})")
        
        # --- [추가] 게이미피케이션 정보 ---
        if st.session_state['logged_in']:
            try:
                # 데이터 로드
                s_df = load_csv(SUGGESTION_FILE, [])
                l_df = load_level_settings()
                
                # 레벨 계산
                lv_name, total_pts, next_lv, pts_need, next_total = calculate_user_level(user_id, s_df, l_df)
                
                st.write(f"**🏅 현재 레벨:** {lv_name}")
                st.write(f"**💰 총 포인트:** {total_pts} P")
                
                if next_lv != "MAX":
                    st.caption(f"다음 레벨({next_lv})까지 {pts_need} P 남음")
                    
                    # 프로그레스 바 계산
                    # (현재점수 - 이전레벨컷) / (다음레벨컷 - 이전레벨컷)
                    l_df['필요점수'] = pd.to_numeric(l_df['필요점수'], errors='coerce')
                    l_df = l_df.sort_values('필요점수', ascending=True)
                    
                    prev_threshold = 0
                    passed = l_df[l_df['필요점수'] <= total_pts]
                    if not passed.empty:
                        prev_threshold = passed.iloc[-1]['필요점수']
                    
                    denom = next_total - prev_threshold
                    if denom > 0:
                        progress = (total_pts - prev_threshold) / denom
                    else:
                        progress = 0.0
                    
                    st.progress(min(max(progress, 0.0), 1.0))
                else:
                    st.success("🎉 최고 레벨 달성!")
                
            except Exception as e:
                st.error(f"레벨 정보 로드 오류: {e}")
            
            st.markdown("---")

        menu_options = ["📝 활동 등록 (공통)"]
        if user_role == "일반":
            menu_options.append("📂 나의 작성 목록")
        elif user_role in ["심사", "Root"]:
            menu_options.append("📊 전체 활동 조회 및 평가")
        if user_role == "Root":
            menu_options.append("⚙️ 시스템 관리")

        menu = st.radio("메뉴 이동", menu_options)
        
        st.markdown("---")
        if st.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.title("🏭 제조 현장 TPM 시스템")

    # ------------------------------------------------
    # [공통] 명예의 전당 (상단 배치)
    # ------------------------------------------------
    st.markdown("### 🏆 명예의 전당")
    col_hof, col_dept = st.columns([1, 1])
    
    # 데이터 로드 (공통 사용)
    df_hof = load_csv(SUGGESTION_FILE, [])
    if not df_hof.empty:
        if '포인트' not in df_hof.columns: df_hof['포인트'] = 0
        # 날짜 컬럼 통일
        if '작성날짜' not in df_hof.columns and '날짜' in df_hof.columns:
            df_hof['작성날짜'] = df_hof['날짜']
        
        # 날짜 타입 변환
        df_hof['date_dt'] = pd.to_datetime(df_hof['작성날짜'], errors='coerce')
        # 포인트 숫자 변환
        df_hof['포인트'] = pd.to_numeric(df_hof['포인트'], errors='coerce').fillna(0)

        # [수정] 부서 정보 추가 (users.csv 매핑)
        if '부서' not in df_hof.columns:
            users_df = load_csv(USER_FILE, ["사번", "부서"])
            if not users_df.empty and '부서' in users_df.columns:
                dept_map = dict(zip(users_df['사번'], users_df['부서']))
                df_hof['부서'] = df_hof['작성자ID'].map(dept_map).fillna("-")
            else:
                df_hof['부서'] = "-"
    
    with col_hof:
        st.markdown("##### 👑 이달의 제안왕 (Top 3)")
        if not df_hof.empty:
            today = datetime.now()
            # 이달의 채택된 제안
            mask_month = (
                (df_hof['date_dt'].dt.year == today.year) & 
                (df_hof['date_dt'].dt.month == today.month) &
                (df_hof['상태'] == '채택')
            )
            df_month = df_hof[mask_month]
            
            if not df_month.empty:
                # 작성자별 합계
                user_ranks = df_month.groupby(['작성자', '부서'])['포인트'].sum().reset_index()
                user_ranks = user_ranks.sort_values('포인트', ascending=False).head(3)
                
                for idx, row in user_ranks.iterrows():
                    medal = ["🥇", "🥈", "🥉"][idx] if idx < 3 else ""
                    st.write(f"**{medal} {idx+1}위**: {row['작성자']} ({row['부서']}) - {int(row['포인트'])} P")
            else:
                st.info(f"{today.month}월 채택된 제안이 아직 없습니다.")
        else:
            st.info("데이터가 없습니다.")
            
    with col_dept:
        st.markdown("##### 🏢 부서별 포인트 랭킹 (누적)")
        if not df_hof.empty:
            # 전체 채택 건
            df_approved = df_hof[df_hof['상태'] == '채택']
            if not df_approved.empty:
                dept_ranks = df_approved.groupby('부서')['포인트'].sum().reset_index()
                dept_ranks = dept_ranks.sort_values('포인트', ascending=False).head(5)
                
                # 차트 표시
                chart = alt.Chart(dept_ranks).mark_bar().encode(
                    x=alt.X('부서', sort='-y', title=None),
                    y=alt.Y('포인트', title=None),
                    color=alt.value('#FFAA00'),
                    tooltip=['부서', '포인트']
                ).properties(height=150)
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("채택된 제안이 없습니다.")
        else:
            st.info("데이터가 없습니다.")
            
    st.divider()

    # ------------------------------------------------
    # [공통] 활동 등록
    # ------------------------------------------------
    if "활동 등록" in menu:
        st.header("📝 개선 활동 등록")
        tab1, tab2 = st.tabs(["💡 제안 제도", "🤝 분임조 활동"])

        with tab1:
            st.write("#### 제안 제도 입력")
            
            s_title = st.text_input("제안 제목")
            
            # --- 리치 텍스트 에디터 ---
            s_content = st_quill(
                placeholder="여기에 내용을 입력하세요.",
                html=True,
                toolbar=[
                    ['bold', 'italic', 'underline', 'strike'],        
                    [{'color': []}, {'background': []}],              
                    [{'header': [1, 2, 3, False]}],                   
                    ['image', 'link'],                                
                    [{'list': 'ordered'}, {'list': 'bullet'}],        
                    ['clean']                                         
                ],
                key="quill_suggestion_create"
            )
            
            st.caption("⚠️ 이미지를 붙여넣거나(Ctrl+V), 도구 모음의 이미지 아이콘을 사용하세요.")

            st.write("") 
            s_file = st.file_uploader("추가 첨부파일 (문서 등)", key="s_file")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                btn_draft = st.button("💾 임시 저장")
            with col2:
                btn_submit = st.button("🚀 제출 (심사 요청)")

            if btn_draft or btn_submit:
                if not s_title or not s_content:
                    st.warning("제목과 내용을 입력해주세요.")
                else:
                    status = "임시저장" if btn_draft else "접수"
                    fname = save_uploaded_file(s_file)
                    new_data = {
                        "ID": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "작성자ID": user_id, "작성자": user_name, "날짜": datetime.now().strftime("%Y-%m-%d"),
                        "제목": s_title, "내용": s_content, "첨부파일": fname, "상태": status
                    }
                    df = load_csv(SUGGESTION_FILE, new_data.keys())
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    save_csv(SUGGESTION_FILE, df)
                    msg = "임시 저장되었습니다." if btn_draft else "제출되었습니다. (상태: 접수)"
                    st.success(f"✅ {msg}")

        with tab2:
            with st.form("c_form"):
                st.write("#### 분임조 활동 입력")
                c_team = st.text_input("분임조명")
                c_content = st.text_area("활동내용")
                c_file = st.file_uploader("활동보고서 파일 첨부")
                
                if st.form_submit_button("등록"):
                    fname_c = save_uploaded_file(c_file)
                    new_data = {
                        "ID": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "작성자ID": user_id, "작성자": user_name, "날짜": datetime.now().strftime("%Y-%m-%d"),
                        "분임조명": c_team, "활동내용": c_content, "첨부파일": fname_c, "상태": "접수"
                    }
                    df = load_csv(CIRCLE_FILE, new_data.keys())
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    save_csv(CIRCLE_FILE, df)
                    st.success("등록되었습니다.")

    # ------------------------------------------------
    # [일반] 나의 작성 목록
    # ------------------------------------------------
    elif "나의 작성 목록" in menu:
        st.header(f"📂 나의 작성 목록 ({user_name})")
        df_s = load_csv(SUGGESTION_FILE, [])
        
        # [Fix] 데이터 일관성 복구 (작성날짜 -> 날짜)
        # 이전 코드의 버그로 인해 파일의 컬럼명이 '작성날짜'로 변경되었을 경우 '날짜'로 복구
        if '작성날짜' in df_s.columns and '날짜' not in df_s.columns:
            df_s.rename(columns={'작성날짜': '날짜'}, inplace=True)
            save_csv(SUGGESTION_FILE, df_s) # 파일에 영구 반영

        if not df_s.empty:
            my_s = df_s[df_s['작성자ID'] == user_id].copy()
            
            # 컬럼 존재 여부 확인 및 초기화
            if '등급' not in my_s.columns:
                my_s['등급'] = "-"
            if '포인트' not in my_s.columns:
                my_s['포인트'] = "0"
            
            # NaN 처리 및 등급 포맷팅
            my_s['등급'] = my_s['등급'].fillna("-").apply(add_grade_emoji)
            my_s['포인트'] = my_s['포인트'].fillna("0")

            # 데이터프레임 표시 (컬럼 추가: 등급, 포인트)
            st.dataframe(
                my_s[['날짜', '제목', '상태', '등급', '포인트']], 
                use_container_width=True,
                column_config={
                    "등급": "평가등급",
                    "포인트": "부여포인트"
                }
            )
            
            st.write("---")
            st.subheader("🛠️ 글 관리 (수정 / 회수 / 삭제)")
            
            post_titles = my_s['제목'].tolist()
            selected_title = st.selectbox("관리할 게시글을 선택하세요", ["선택안함"] + post_titles)
            
            if selected_title != "선택안함":
                row = my_s[my_s['제목'] == selected_title].iloc[0]
                current_id = row['ID']
                current_status = row['상태']
                
                st.info(f"선택된 글: **{row['제목']}** (상태: {current_status})")
                
                # --- [수정] 버튼 배치 (회수 | 삭제) ---
                col_recall, col_del, col_space = st.columns([1, 1, 4])
                
                if current_status in ["접수", "심사대기"]:
                    with col_recall:
                        if st.button("↩️ 회수하기"):
                            st.session_state['recall_confirm_id'] = current_id
                
                with col_del:
                    if st.button("🗑️ 삭제하기", type="primary"):
                        st.session_state['delete_confirm_id'] = current_id

                # --- 팝업 (회수) ---
                if st.session_state['recall_confirm_id'] == current_id:
                    with st.container(border=True):
                        st.warning(f"⚠️ 이미 제출된 '{current_status}' 상태입니다.\n회수하면 '임시저장' 상태로 변경됩니다. 진행하시겠습니까?")
                        col_y, col_n = st.columns(2)
                        if col_y.button("네, 회수합니다", key="recall_yes"):
                            idx = df_s.index[df_s['ID'] == current_id].tolist()[0]
                            df_s.at[idx, '상태'] = "임시저장"
                            save_csv(SUGGESTION_FILE, df_s)
                            st.session_state['recall_confirm_id'] = None
                            st.success("✅ 회수되었습니다. 내용을 수정한 뒤 다시 제출하세요.")
                            time.sleep(1)
                            st.rerun()
                        if col_n.button("취소", key="recall_no"):
                            st.session_state['recall_confirm_id'] = None
                            st.rerun()

                # --- 팝업 (삭제) ---
                if st.session_state['delete_confirm_id'] == current_id:
                    with st.container(border=True):
                        st.error("⚠️ 정말로 이 게시글을 삭제하시겠습니까? (복구 불가)")
                        col_y, col_n = st.columns(2)
                        if col_y.button("네, 삭제합니다", key="del_yes"):
                            df_new = df_s[df_s['ID'] != current_id]
                            save_csv(SUGGESTION_FILE, df_new)
                            st.session_state['delete_confirm_id'] = None
                            st.success("삭제되었습니다!")
                            time.sleep(1)
                            st.rerun()
                        if col_n.button("아니오", key="del_no"):
                            st.session_state['delete_confirm_id'] = None
                            st.rerun()

                st.write("---")

                # --- 수정 에디터 (임시저장, 접수, 심사대기 상태일 때) ---
                if current_status in ["임시저장", "접수", "심사대기"]:
                    st.write("#### ✏️ 내용 수정")
                    new_title = st.text_input("제목 수정", value=row['제목'])
                    
                    new_content = st_quill(
                        value=row['내용'],
                        html=True,
                        toolbar=[['bold', 'italic'], [{'header': [1, 2, False]}], ['image', 'link'], ['clean']],
                        key=f"edit_quill_{current_id}"
                    )
                    
                    # [수정] 수정 화면에도 버튼 분리 적용 (임시저장 / 제출)
                    col_edit_1, col_edit_2 = st.columns([1, 1])
                    with col_edit_1:
                        btn_edit_draft = st.button("💾 임시 저장 (수정)")
                    with col_edit_2:
                        btn_edit_submit = st.button("🚀 제출 (심사 요청)")

                    if btn_edit_draft or btn_edit_submit:
                        idx = df_s.index[df_s['ID'] == current_id].tolist()[0]
                        
                        # 내용 업데이트
                        df_s.at[idx, '제목'] = new_title
                        df_s.at[idx, '내용'] = new_content
                        
                        # 버튼에 따른 상태 변경 로직
                        if btn_edit_draft:
                            df_s.at[idx, '상태'] = "임시저장"
                            msg = "임시 저장되었습니다."
                        else:
                            df_s.at[idx, '상태'] = "접수" # 제출 시 접수 상태로 변경
                            msg = "제출되었습니다. (상태: 접수)"

                        save_csv(SUGGESTION_FILE, df_s)
                        st.success(f"✅ {msg}")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.warning(f"현재 상태('{current_status}')에서는 수정할 수 없습니다.")
                    st.write("### 📄 작성 내용 (읽기 전용)")
                    st.markdown(row['내용'], unsafe_allow_html=True)

    # ------------------------------------------------
    # [심사/Root] 전체 활동 조회 및 평가
    # ------------------------------------------------
    elif "전체 활동 조회 및 평가" in menu:
        st.header("📊 전체 활동 현황")
        df_s = load_csv(SUGGESTION_FILE, [])
        
        # [수정] 컬럼명 변경 (점수 -> 포인트) 및 초기화
        if '점수' in df_s.columns and '포인트' not in df_s.columns:
            df_s.rename(columns={'점수': '포인트'}, inplace=True)

        if '등급' not in df_s.columns:
            df_s['등급'] = ""
        if '포인트' not in df_s.columns:
            df_s['포인트'] = 0
        if '평가점수' not in df_s.columns:
            df_s['평가점수'] = 0

        if not df_s.empty:
            # [수정] 날짜 열 이름 변경
            if '날짜' in df_s.columns:
                df_s.rename(columns={'날짜': '작성날짜'}, inplace=True)
            
            # [수정] '반려' 상태를 '미채택'으로 일괄 변경 (기존 데이터 호환성)
            if '상태' in df_s.columns:
                df_s['상태'] = df_s['상태'].replace('반려', '미채택')

            # [수정] 부서 정보 추가
            users_df = load_csv(USER_FILE, ["사번", "부서"])
            if not users_df.empty and '부서' in users_df.columns:
                dept_map = dict(zip(users_df['사번'], users_df['부서']))
                df_s['부서'] = df_s['작성자ID'].map(dept_map).fillna("-")
            else:
                df_s['부서'] = "-"

            # --- [추가] 부서별 접수 현황 그래프 (당해년도 / 당월) ---
            st.markdown("#### 📈 부서별 활동 현황")
            
            # 지정된 부서 순서
            target_depts = ["생산1팀", "생산2팀", "생산3팀", "품질관리팀", "공무팀", "연구소"]
            
            # 날짜 처리를 위한 준비
            today = datetime.now()
            current_year = today.year
            current_month = today.month

            if '작성날짜' in df_s.columns:
                df_s['temp_date_obj'] = pd.to_datetime(df_s['작성날짜'], errors='coerce')
                
                # 1. 당해년도 데이터 집계 (전체 -> 당해년도)
                year_mask = (df_s['temp_date_obj'].dt.year == current_year)
                df_year = df_s[year_mask]
                dept_counts_year = df_year['부서'].value_counts().reindex(target_depts, fill_value=0)
                
                # 2. 당월 데이터 집계
                month_mask = (
                    (df_s['temp_date_obj'].dt.year == current_year) & 
                    (df_s['temp_date_obj'].dt.month == current_month)
                )
                df_month = df_s[month_mask]
                dept_counts_month = df_month['부서'].value_counts().reindex(target_depts, fill_value=0)
            else:
                dept_counts_year = pd.Series(0, index=target_depts)
                dept_counts_month = pd.Series(0, index=target_depts)

            # Altair 차트 생성 함수
            def make_bar_chart(data_series, title_text, bar_color):
                # DataFrame 변환
                chart_data = pd.DataFrame({
                    '부서': data_series.index,
                    '건수': data_series.values
                })
                
                # 기본 차트 설정
                base = alt.Chart(chart_data).encode(
                    x=alt.X('부서', sort=target_depts, axis=alt.Axis(labelAngle=0, title=None)),
                    y=alt.Y('건수', axis=None), # Y축 눈금 제거 (깔끔하게)
                    tooltip=['부서', '건수']
                )
                
                # 막대 그래프
                bars = base.mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
                    color=alt.value(bar_color)
                )
                
                # 텍스트 레이블 (건수 표시)
                text = base.mark_text(
                    align='center',
                    baseline='bottom',
                    dy=-5,  # 막대 위로 띄우기
                    fontSize=12,
                    fontWeight='bold'
                ).encode(
                    text='건수'
                )
                
                # 최종 차트 결합 및 스타일
                final_chart = (bars + text).properties(
                    title=title_text,
                    height=250
                ).configure_view(
                    strokeWidth=0 # 테두리 제거
                ).configure_axis(
                    grid=False, # 그리드 제거
                    domain=False
                )
                
                return final_chart

            # 그래프 표시 (2단 컬럼)
            g_col1, g_col2 = st.columns(2)
            
            with g_col1:
                st.altair_chart(
                    make_bar_chart(dept_counts_year, f"📅 전체 누적 접수 ({current_year}년)", "#4c78a8"),
                    use_container_width=True
                )
            
            with g_col2:
                st.altair_chart(
                    make_bar_chart(dept_counts_month, f"📆 당월 접수 ({current_month}월)", "#f58518"),
                    use_container_width=True
                )

            st.write("---")
            
            # --- 조회(필터링) 기능 추가 ---
            with st.expander("🔍 상세 조회 옵션", expanded=True):
                col_f1, col_f2, col_f3 = st.columns(3)
                
                with col_f1:
                    # 날짜 범위 설정 (기본값: 최근 30일)
                    today = datetime.now()
                    start_date_val = today - pd.Timedelta(days=30)
                    date_range = st.date_input(
                        "작성 날짜 범위",
                        value=(start_date_val, today),
                        key="filter_date_range"
                    )
                
                with col_f2:
                    filter_name = st.text_input("작성자 이름", key="filter_name")
                    filter_title = st.text_input("제목 (키워드)", key="filter_title")
                
                with col_f3:
                    # 상태 목록 추출 (기존 데이터 기반 + 기본값)
                    all_statuses = ["전체"] + sorted(list(set(df_s['상태'].unique()) | {"접수", "심사대기", "채택", "미채택"}))
                    filter_status = st.selectbox("진행 상태", all_statuses, key="filter_status")
                    
                    # 등급 목록 (기존 데이터 기반)
                    # [수정] TypeError 방지를 위해 모든 값을 문자열로 변환하고 NaN/빈값 제외
                    unique_grades = df_s['등급'].unique()
                    valid_grades = [str(g) for g in unique_grades if pd.notna(g) and str(g).strip() != ""]
                    all_grades = ["전체"] + sorted(valid_grades)
                    
                    filter_grade = st.selectbox("등급", all_grades, key="filter_grade")

            # --- 필터링 로직 적용 ---
            # 1. 날짜 필터
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_d, end_d = date_range
                # 문자열 날짜를 비교하기 위해 형변환 혹은 문자열 비교 (YYYY-MM-DD 형식 가정)
                # 데이터의 날짜 형식이 YYYY-MM-DD 라고 가정
                df_s['temp_date'] = pd.to_datetime(df_s['작성날짜'], errors='coerce').dt.date
                df_s = df_s[
                    (df_s['temp_date'] >= start_d) & 
                    (df_s['temp_date'] <= end_d)
                ]
            
            # 2. 이름 필터
            if filter_name:
                df_s = df_s[df_s['작성자'].str.contains(filter_name, na=False)]
            
            # 3. 제목 필터
            if filter_title:
                df_s = df_s[df_s['제목'].str.contains(filter_title, na=False)]
            
            # 4. 상태 필터
            if filter_status != "전체":
                df_s = df_s[df_s['상태'] == filter_status]
            
            # 5. 등급 필터
            if filter_grade != "전체":
                df_s = df_s[df_s['등급'] == filter_grade]

            # --- 페이지네이션 (Pagination) 설정 ---
            if 'page_number' not in st.session_state:
                st.session_state['page_number'] = 1
                
            ROWS_PER_PAGE = 15
            total_rows = len(df_s)
            total_pages = (total_rows - 1) // ROWS_PER_PAGE + 1
            
            # 페이지 번호가 범위를 벗어나지 않도록 조정
            if st.session_state['page_number'] > total_pages:
                st.session_state['page_number'] = max(1, total_pages)
                
            current_page = st.session_state['page_number']
            start_idx = (current_page - 1) * ROWS_PER_PAGE
            end_idx = start_idx + ROWS_PER_PAGE
            
            # 현재 페이지에 표시할 데이터 슬라이싱
            df_display = df_s.iloc[start_idx:end_idx].copy()
            
            # [추가] 작성자 레벨(누적 포인트 기준) 계산
            try:
                # 전체 데이터를 기준으로 포인트 합산
                df_all = load_csv(SUGGESTION_FILE, [])
                if '포인트' in df_all.columns:
                    df_all['포인트'] = pd.to_numeric(df_all['포인트'], errors='coerce').fillna(0)
                    user_total_points = df_all[df_all['상태'] == '채택'].groupby('작성자ID')['포인트'].sum().to_dict()
                else:
                    user_total_points = {}
                
                level_settings = load_level_settings()
                level_settings['필요점수'] = pd.to_numeric(level_settings['필요점수'], errors='coerce')
                level_settings = level_settings.sort_values('필요점수', ascending=True)
                
                def get_author_level(uid):
                    pts = user_total_points.get(uid, 0)
                    lv_name = "새싹"
                    emoji = "🌱"
                    has_emoji = '이모지' in level_settings.columns
                    
                    for _, r in level_settings.iterrows():
                        if pts >= r['필요점수']:
                            lv_name = r['등급명']
                            if has_emoji: emoji = r['이모지']
                    return f"{emoji} {lv_name}"
                
                df_display['작성자등급'] = df_display['작성자ID'].apply(get_author_level)
            except Exception:
                df_display['작성자등급'] = "-"

            # 평가 등급(S~C) 이모지 적용
            df_display['평가등급'] = df_display['등급'].apply(add_grade_emoji)

            # [수정] 상태별 글자 색상 적용 (Pandas Styler)
            def color_status_text(val):
                if val == '미채택': return 'color: red; font-weight: bold;'
                if val == '심사대기': return 'color: orange; font-weight: bold;'
                if val == '접수': return 'color: blue;'
                if val == '채택': return 'color: green; font-weight: bold;'
                return ''

            # 데이터프레임 표시 (작성자등급 컬럼 추가, 등급 -> 평가등급 변경)
            st.dataframe(
                df_display[['작성자', '작성자등급', '부서', '작성날짜', '제목', '상태', '평가등급', '포인트', '평가점수']].style.applymap(color_status_text, subset=['상태']),
                use_container_width=True
            )
            
            # --- 페이지네이션 UI (하단 번호) ---
            if total_pages > 1:
                st.write("---")
                # 중앙 정렬을 위해 컬럼 사용
                _, col_center, _ = st.columns([1, 2, 1])
                with col_center:
                    # 페이지 번호 버튼 생성
                    # 번호가 많을 경우 처리가 필요하지만, 여기서는 간단히 10개 단위 혹은 전체 표시
                    # Streamlit 버튼은 클릭 시 rerun되므로 콜백으로 페이지 상태 변경
                    
                    def set_page(i):
                        st.session_state['page_number'] = i
                    
                    # 이전, 다음 버튼과 페이지 번호들을 나열
                    # 10페이지 이상일 경우 슬라이딩 윈도우 방식이 좋으나 여기선 단순 나열
                    cols = st.columns(min(total_pages + 2, 12)) # 최대 12개 컬럼 제한
                    
                    # [이전] 버튼
                    if current_page > 1:
                        if cols[0].button("◀", key="prev_page"):
                            set_page(current_page - 1)
                            st.rerun()
                    
                    # 페이지 번호 버튼들 (현재 페이지 주변 보여주기 등 로직 간소화: 전체 표시 시도하되 많으면 끊기)
                    # 여기서는 간단히 1~10페이지까지만 표시하거나 전체 표시 (사용자 요청: mail함 처럼)
                    # 전체를 다 보여주기엔 칸이 모자랄 수 있으므로 현재 페이지 중심으로 표시
                    
                    start_p = max(1, current_page - 4)
                    end_p = min(total_pages, start_p + 9)
                    
                    col_idx = 1
                    for p in range(start_p, end_p + 1):
                        if col_idx < len(cols) - 1:
                            if cols[col_idx].button(f"{p}", key=f"page_{p}", type="primary" if p == current_page else "secondary"):
                                set_page(p)
                                st.rerun()
                            col_idx += 1
                            
                    # [다음] 버튼
                    if current_page < total_pages:
                        if cols[col_idx].button("▶", key="next_page"):
                            set_page(current_page + 1)
                            st.rerun()

            st.caption(f"총 {total_rows}건 중 {start_idx + 1} - {min(end_idx, total_rows)}건 표시 (Page {current_page}/{total_pages})")
            
            st.write("---")
            st.subheader("🔎 상세 내용 검토")
            # 검토 대상 선택 박스에는 필터링된 목록만 표시
            review_title = st.selectbox("검토할 제안 선택", ["선택안함"] + df_s['제목'].unique().tolist())
            
            if review_title != "선택안함":
                row = df_s[df_s['제목'] == review_title].iloc[0]
                st.write(f"**작성자:** {row['작성자']} | **상태:** {row['상태']}")
                st.markdown(row['내용'], unsafe_allow_html=True)
                
                # 심사 기능
                if user_role in ["심사", "Root"]:
                    st.write("---")
                    st.markdown("#### 📝 등급 평가")
                    
                    # 평가 항목 (라디오 버튼)
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        st.markdown("##### **창의성 (30점)**")
                        sc_creative = st.radio("창의성", [0, 10, 20, 30], horizontal=True, label_visibility="collapsed", key=f"sc_c_{row['ID']}", format_func=lambda x: f"{x}점")
                        
                        st.markdown("##### **효과성 (30점)**")
                        sc_effective = st.radio("효과성", [0, 10, 20, 30], horizontal=True, label_visibility="collapsed", key=f"sc_e_{row['ID']}", format_func=lambda x: f"{x}점")
                        
                        st.markdown("##### **실행성 (20점)**")
                        sc_execute = st.radio("실행성", [0, 10, 15, 20], horizontal=True, label_visibility="collapsed", key=f"sc_x_{row['ID']}", format_func=lambda x: f"{x}점")
                    
                    with e_col2:
                        st.markdown("##### **지속성 (10점)**")
                        sc_sustain = st.radio("지속성", [0, 5, 10], horizontal=True, label_visibility="collapsed", key=f"sc_s_{row['ID']}", format_func=lambda x: f"{x}점")
                        
                        st.markdown("##### **표준화기여도 (10점)**")
                        sc_standard = st.radio("표준화기여도", [0, 5, 10], horizontal=True, label_visibility="collapsed", key=f"sc_t_{row['ID']}", format_func=lambda x: f"{x}점")
                    
                    total_score = sc_creative + sc_effective + sc_execute + sc_sustain + sc_standard
                    
                    # 평가 등급 산정 로직 (S: 90~100, A: 70~89, B: 60~69, C: 60미만)
                    if total_score >= 90:
                        grade = "S"
                        grade_points = 20
                    elif total_score >= 70:
                        grade = "A"
                        grade_points = 10
                    elif total_score >= 60:
                        grade = "B"
                        grade_points = 5
                    else:
                        grade = "C"
                        grade_points = 1
                        
                    st.info(f"📊 **총점: {total_score}점**  👉  **등급: {grade}** (부여 포인트: {grade_points})")
                    
                    # 승인/반려 버튼
                    col_approve, col_reject = st.columns([1, 1])
                    with col_approve:
                        if st.button("✅ 채택 (승인)"):
                            idx = df_s.index[df_s['ID'] == row['ID']].tolist()[0]
                            df_s.at[idx, '상태'] = "채택"
                            df_s.at[idx, '등급'] = grade
                            df_s.at[idx, '포인트'] = grade_points
                            df_s.at[idx, '평가점수'] = total_score
                            
                            # 저장 시 '작성날짜'를 '날짜'로 원복하여 저장
                            df_save = df_s.copy()
                            if '작성날짜' in df_save.columns:
                                df_save.rename(columns={'작성날짜': '날짜'}, inplace=True)
                            save_csv(SUGGESTION_FILE, df_save)
                            
                            st.success(f"채택 처리되었습니다. (등급: {grade}, 포인트: {grade_points}, 평가총점: {total_score}점)")
                            time.sleep(1)
                            st.rerun()
                    
                    with col_reject:
                        if st.button("❌ 미채택"):
                            idx = df_s.index[df_s['ID'] == row['ID']].tolist()[0]
                            df_s.at[idx, '상태'] = "미채택"
                            
                            # 저장 시 '작성날짜'를 '날짜'로 원복하여 저장
                            df_save = df_s.copy()
                            if '작성날짜' in df_save.columns:
                                df_save.rename(columns={'작성날짜': '날짜'}, inplace=True)
                            save_csv(SUGGESTION_FILE, df_save)
                            
                            st.warning("미채택 처리되었습니다.")
                            st.rerun()

                if user_role == "Root":
                    if st.button("🗑️ 관리자 권한 삭제"):
                        df_s = df_s[df_s['ID'] != row['ID']]
                        
                        # 저장 시 '작성날짜'를 '날짜'로 원복하여 저장
                        df_save = df_s.copy()
                        if '작성날짜' in df_save.columns:
                            df_save.rename(columns={'작성날짜': '날짜'}, inplace=True)
                        save_csv(SUGGESTION_FILE, df_save)
                        
                        st.error("관리자 권한으로 삭제되었습니다.")
                        st.rerun()

    # ------------------------------------------------
    # [Root] 시스템 관리
    # ------------------------------------------------
    elif "시스템 관리" in menu:
        st.header("⚙️ 시스템 관리자 페이지")
        
        tab_users, tab_levels = st.tabs(["👥 회원 관리", "🏆 레벨 기준 설정"])
        
        # [Tab 1] 회원 관리
        with tab_users:
            users = load_csv(USER_FILE, ["사번", "비밀번호", "이름", "권한", "부서", "직책", "가입날짜"])
            
            # 체크박스 컬럼 추가 (관리자 계정 제외)
            users_display = users.copy()
            if '선택' not in users_display.columns:
                users_display.insert(0, '선택', False)
            
            # 관리자 계정은 체크박스 비활성화 (False로 고정)
            users_display.loc[users_display['사번'] == 'administrator', '선택'] = False
            
            # 체크박스 선택 상태 초기화
            if 'user_selections' not in st.session_state:
                st.session_state['user_selections'] = {}
            
            # data_editor로 표시
            edited_users = st.data_editor(
                users_display,
                num_rows="dynamic",
                column_config={
                    "선택": st.column_config.CheckboxColumn(
                        "선택",
                        help="삭제할 계정을 선택하세요",
                        default=False,
                    ),
                    "사번": st.column_config.TextColumn("사번", disabled=True),
                    "비밀번호": st.column_config.TextColumn("비밀번호"),
                    "이름": st.column_config.TextColumn("이름"),
                    "권한": st.column_config.SelectboxColumn(
                        "권한",
                        options=["일반", "심사", "Root"],
                    ),
                    "부서": st.column_config.TextColumn("부서"),
                    "직책": st.column_config.TextColumn("직책"),
                    "가입날짜": st.column_config.TextColumn("가입날짜"),
                },
                hide_index=True,
            )
            
            # 선택된 계정 확인
            selected_rows = edited_users[
                (edited_users['선택'] == True) & 
                (edited_users['사번'] != 'administrator')
            ]
            
            selected_user_ids = []
            selected_indices = []
            for idx, row in selected_rows.iterrows():
                user_id = row['사번']
                if pd.isna(user_id) or user_id == '' or str(user_id).strip() == 'nan':
                    selected_indices.append(idx)
                else:
                    selected_user_ids.append(str(user_id))
            
            total_selected_display = len(selected_user_ids) + len(selected_indices)
            if total_selected_display > 0:
                st.info(f"선택된 계정: {total_selected_display}개")
            
            col_save, col_delete = st.columns([1, 1])
            with col_save:
                if st.button("회원 정보 수정 저장"):
                    st.info("회원 정보는 위 목록에서 직접 수정할 수 없습니다. 개별 수정이 필요하면 관리자에게 문의하세요.")
            
            with col_delete:
                total_selected = len(selected_user_ids) + len(selected_indices)
                delete_clicked = st.button("🗑️ 계정삭제", type="primary", disabled=total_selected == 0)
                if delete_clicked:
                    if total_selected > 0:
                        st.session_state['admin_delete_confirm'] = True
                        st.session_state['admin_delete_user_id'] = selected_user_ids
                        st.session_state['admin_delete_indices'] = selected_indices
                        st.rerun()
                    else:
                        st.warning("삭제할 계정을 선택해주세요.")
            
            # 계정 삭제 팝업
            if st.session_state.get('admin_delete_confirm', False):
                st.write("---")
                with st.container(border=True):
                    st.subheader("⚠️ 계정 삭제 확인")
                    
                    selected_ids = st.session_state.get('admin_delete_user_id', [])
                    selected_indices = st.session_state.get('admin_delete_indices', [])
                    total_to_delete = len(selected_ids) + len(selected_indices)
                    
                    if total_to_delete > 0:
                        st.warning(f"**삭제할 계정 ({total_to_delete}개):**")
                        
                        if selected_ids:
                            selected_users_info = users[users['사번'].isin(selected_ids)][['사번', '이름']]
                            for _, user_row in selected_users_info.iterrows():
                                user_name = user_row.get('이름', '') if pd.notna(user_row.get('이름', '')) else user_row['사번']
                                st.write(f"- {user_name} ({user_row['사번']})")
                        
                        if selected_indices:
                            for idx in selected_indices:
                                if idx < len(users):
                                    row = users.iloc[idx]
                                    st.write(f"- 빈 항목 (행 {idx + 1})")
                        
                        st.error("⚠️ 이 작업은 되돌릴 수 없습니다!")
                        
                        current_admin_id = st.session_state.get('user_id', '')
                        current_admin_name = st.session_state.get('user_name', '')
                        admin_pw = st.text_input(f"{current_admin_name}님의 비밀번호를 입력하세요", type="password", key="admin_pw_confirm")
                        
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ 삭제 확인", type="primary", key="delete_confirm_btn"):
                                current_admin = users[users['사번'] == current_admin_id]
                                if not current_admin.empty:
                                    current_admin = current_admin.iloc[0]
                                    if current_admin['비밀번호'] == admin_pw:
                                        if selected_ids:
                                            users = users[~users['사번'].isin(selected_ids)]
                                        
                                        if selected_indices:
                                            sorted_indices = sorted(selected_indices, reverse=True)
                                            for idx in sorted_indices:
                                                if idx < len(users):
                                                    users = users.drop(users.index[idx]).reset_index(drop=True)
                                        
                                        save_csv(USER_FILE, users)
                                        
                                        st.session_state['admin_delete_confirm'] = False
                                        st.session_state['admin_delete_user_id'] = None
                                        st.session_state['admin_delete_indices'] = None
                                        st.success(f"✅ {total_to_delete}개 계정이 삭제되었습니다.")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("❌ 비밀번호가 일치하지 않습니다.")
                                else:
                                    st.error("❌ 현재 로그인된 계정을 찾을 수 없습니다.")
                        
                        with col_no:
                            if st.button("❌ 취소", key="delete_cancel_btn"):
                                st.session_state['admin_delete_confirm'] = False
                                st.session_state['admin_delete_user_id'] = None
                                st.session_state['admin_delete_indices'] = None
                                st.rerun()

        # [Tab 2] 레벨 기준 설정
        with tab_levels:
            st.subheader("🏆 레벨 기준 및 필요 점수 설정")
            st.info("각 레벨의 이름과 도달하기 위한 최소 점수를 설정합니다.")
            
            level_df = load_level_settings()
            
            # 데이터 에디터 (행 추가/삭제 가능)
            edited_level_df = st.data_editor(
                level_df,
                num_rows="dynamic",
                column_config={
                    "이모지": st.column_config.TextColumn("이모지", width="small"),
                    "등급명": st.column_config.TextColumn("등급명", required=True),
                    "필요점수": st.column_config.NumberColumn("필요 점수", required=True, min_value=0, format="%d"),
                },
                use_container_width=True,
                key="level_settings_editor"
            )
            
            if st.button("💾 레벨 설정 저장"):
                if edited_level_df is not None and not edited_level_df.empty:
                    # 필수 컬럼 확인
                    if '등급명' in edited_level_df.columns and '필요점수' in edited_level_df.columns:
                        # 점수 기준 오름차순 정렬
                        edited_level_df['필요점수'] = pd.to_numeric(edited_level_df['필요점수'], errors='coerce').fillna(0)
                        edited_level_df = edited_level_df.sort_values('필요점수', ascending=True)
                        
                        # 저장
                        edited_level_df.to_csv(LEVEL_SETTINGS_FILE, index=False)
                        st.success("✅ 레벨 설정이 저장되었습니다. (즉시 반영됨)")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 데이터에 '등급명', '필요점수' 컬럼이 있어야 합니다.")
                else:
                    st.warning("저장할 데이터가 없습니다.")

# --- 프로그램 실행 ---
if st.session_state['logged_in']:
    main_app()
else:
    login_page()
