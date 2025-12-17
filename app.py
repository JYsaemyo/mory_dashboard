import streamlit as st
import paho.mqtt.client as mqtt
import pymysql
import pandas as pd
import time
import ssl

# --- 페이지 설정 ---
st.set_page_config(page_title="Mory Controller", layout="wide", page_icon="🕹️")

# --- [설정] secrets.toml 로드 ---
try:
    # MQTT (속도 조절용)
    HIVEMQ_BROKER = st.secrets["mqtt"]["broker"]
    HIVEMQ_PORT = st.secrets["mqtt"]["port"]
    HIVEMQ_USERNAME = st.secrets["mqtt"]["username"]
    HIVEMQ_PASSWORD = st.secrets["mqtt"]["password"]
    # 제어 명령을 보낼 토픽 (예: robot/control)
    # 기존 GPS 토픽과 겹치지 않게 주의하세요. 필요시 수정!
    CONTROL_TOPIC = "robot/mory_gps/control" 
    
    # MySQL (퀴즈 분석용)
    MYSQL_HOST = st.secrets["mysql"]["host"]
    MYSQL_PORT = st.secrets["mysql"]["port"]
    MYSQL_USER = st.secrets["mysql"]["user"]
    MYSQL_PASSWORD = st.secrets["mysql"]["password"]
    MYSQL_DB = st.secrets["mysql"]["name"]
except Exception as e:
    st.error(f"❌ 설정 로드 오류: secrets.toml을 확인해주세요. ({e})")
    st.stop()

# ==========================================
# 공통 함수 및 설정
# ==========================================

# ==========================================
# 1. MQTT 클라이언트 초기화 (오류 수정 버전)
# ==========================================
if 'mqtt_client' not in st.session_state:
    
    # [수정됨] 인자 5개로 맞춤 (Version 2 필수)
    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("✅ [디버그] MQTT 브로커 연결 성공!")
            st.session_state['mqtt_connected'] = True
        else:
            print(f"❌ [디버그] 연결 실패. 코드: {reason_code}")
            st.session_state['mqtt_connected'] = False

    # [★여기가 문제였습니다★] 인자를 5개로 늘려야 합니다.
    def on_publish(client, userdata, mid, reason_code, properties):
        print(f"📡 [디버그] 메시지 전송 성공 (Message ID: {mid})")

    # 클라이언트 설정
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Streamlit_Controller_Fix")
    client.username_pw_set(HIVEMQ_USERNAME, HIVEMQ_PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
    
    # 콜백 연결
    client.on_connect = on_connect
    client.on_publish = on_publish

    # 접속 시도
    try:
        client.connect(HIVEMQ_BROKER, HIVEMQ_PORT, 60)
        client.loop_start() 
        st.session_state['mqtt_client'] = client
        st.session_state['mqtt_status'] = "Connecting..."
        time.sleep(1) # 연결 대기
    except Exception as e:
        st.error(f"MQTT 접속 에러: {e}")

# 연결 상태 표시
if st.session_state.get('mqtt_connected'):
    st.sidebar.success("MQTT: 연결됨 (Ready)")
else:
    st.sidebar.warning("MQTT: 연결 중...")

# 2. DB 연결 함수
def get_db_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# ==========================================
# 사이드바 메뉴
# ==========================================
with st.sidebar:
    st.title("🎛️ 메뉴 선택")
    page = st.radio("이동할 페이지:", ["🎮 속도 조절 (Controller)", "📊 퀴즈 성적 분석 (DB)"])
    
    st.divider()
    st.caption(f"MQTT Status: {st.session_state.get('mqtt_status', 'Unknown')}")

# ==========================================
# PAGE 1: 속도 조절 (Controller)
# ==========================================
if page == "🎮 속도 조절 (Controller)":
    st.header("🎮 로봇 속도 제어")
    st.info(f"명령 전송 토픽: `{CONTROL_TOPIC}`")

    # 버튼 레이아웃
    col1, col2 = st.columns(2)
    
    # 메시지 전송 함수
    def send_command(msg):
        client = st.session_state.get('mqtt_client')
        if client:
            client.publish(CONTROL_TOPIC, msg)
            st.toast(f"🚀 전송 완료: {msg}", icon="✅")
        else:
            st.error("MQTT가 연결되지 않았습니다.")

    with col1:
        st.write("### ⚡ Speed UP")
        if st.button("➕ 속도 증가", type="primary", use_container_width=True, key="btn_up"):
            send_command("speed up")

    with col2:
        st.write("### 🐢 Speed DOWN")
        if st.button("➖ 속도 감소", use_container_width=True, key="btn_down"):
            send_command("speed down")
            
    st.divider()
    st.markdown("**사용 가이드:**")
    st.markdown("- **(+) 버튼**: Jetson 보드로 `speed up` 메시지를 보냅니다.")
    st.markdown("- **(-) 버튼**: Jetson 보드로 `speed down` 메시지를 보냅니다.")

# ==========================================
# PAGE 2: 퀴즈 성적 분석 (DB)
# ==========================================
elif page == "📊 퀴즈 성적 분석 (DB)":
    st.header("📊 퀴즈 성적 분석 & 기록")

    if st.button("🔄 데이터 새로고침"):
        st.rerun()

    # 데이터 가져오기 로직 (경고 해결 버전)
    def fetch_logs():
        try:
            conn = get_db_connection()
            # 1. 커서를 이용해서 직접 쿼리 실행
            with conn.cursor() as cursor:
                query = "SELECT * FROM server_quiz_logs ORDER BY id DESC LIMIT 500"
                cursor.execute(query)
                result = cursor.fetchall() # 데이터를 리스트(딕셔너리) 형태로 다 가져옴
            
            conn.close()
            
            # 2. 가져온 리스트를 DataFrame으로 변환 (이러면 경고가 안 뜹니다)
            return pd.DataFrame(result)
            
        except Exception as e:
            st.error(f"DB 연결 실패: {e}")
            return pd.DataFrame()

    raw_df = fetch_logs()

    if not raw_df.empty:
        # --- 그래프 분석 로직 (5문제 = 1회차) ---
        df_sorted = raw_df.sort_values(by='id', ascending=True).reset_index(drop=True)
        df_sorted['round_num'] = (df_sorted.index // 5) + 1
        
        round_stats = df_sorted.groupby('round_num')['is_correct'].sum().reset_index()
        round_stats.columns = ['회차', '점수 (5점 만점)']
        chart_data = round_stats.set_index('회차')

        st.subheader("📈 회차별 점수 (5문제 단위)")
        st.bar_chart(chart_data, color="#3B82F6")
        
        # --- 상세 테이블 로직 ---
        st.divider()
        st.subheader("📝 상세 문제 풀이 내역")
        
        st.dataframe(
            raw_df, # 원본(최신순) 표시
            use_container_width=True,
            column_config={
                "id": "ID",
                "question": "문제",
                "truth": "정답",
                "user_answer": "제출 답안",
                "is_correct": st.column_config.CheckboxColumn("정답 여부"),
                "created_at": st.column_config.DatetimeColumn("제출 시간", format="MM-DD HH:mm")
            },
            hide_index=True
        )
    else:
        st.info("데이터가 없습니다.")
