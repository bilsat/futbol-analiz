import math, requests, numpy as np, pandas as pd, streamlit as st, plotly.express as px
from datetime import datetime

# ======================================================
# ⚽ API AYARLARI (CEP/WEB SÜRÜMÜ)
# ======================================================
API_KEY = "d879308f24518901a28a73d174fa6a12"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY,
    "User-Agent": "Mozilla/5.0"
}

# ======================================================
# 🔧 Yardımcı Fonksiyonlar
# ======================================================
@st.cache_data(ttl=600)
def get_data(endpoint, params=None):
    try:
        r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=20)
        if r.status_code == 200:
            return r.json().get("response", [])
        else:
            return []
    except Exception:
        return []

def safe_div(a, b): return a / b if b else 0
def poisson_p(k, lam): return math.exp(-lam) * (lam ** k) / math.factorial(k)
def poisson_matrix(lh, la, max_g=6):
    M = np.zeros((max_g+1, max_g+1))
    for i in range(max_g+1):
        for j in range(max_g+1):
            M[i,j] = poisson_p(i, lh) * poisson_p(j, la)
    return M
def over25_prob(M): return np.add.outer(np.arange(M.shape[0]), np.arange(M.shape[1]))[M>0].sum()/M.sum()
def btts_prob(M):
    p=0
    for i in range(1,M.shape[0]):
        for j in range(1,M.shape[1]):
            p+=M[i,j]
    return p
def wdl_from_poisson(M):
    ph=pdx=pa=0
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if i>j: ph+=M[i,j]
            elif i==j: pdx+=M[i,j]
            else: pa+=M[i,j]
    return ph,pdx,pa
def team_form(fixtures, team_id):
    W=D=L=gf=ga=0
    for f in fixtures:
        goals=f.get("goals",{}) or {}
        if goals=={}: continue
        is_home=f.get("teams",{}).get("home",{}).get("id")==team_id
        gfor=goals.get("home") if is_home else goals.get("away")
        gagt=goals.get("away") if is_home else goals.get("home")
        gfor=gfor if isinstance(gfor,(int,float)) else 0
        gagt=gagt if isinstance(gagt,(int,float)) else 0
        gf+=gfor; ga+=gagt
        if gfor>gagt: W+=1
        elif gfor==gagt: D+=1
        else: L+=1
    n=len(fixtures) if fixtures else 1
    return {"W":W,"D":D,"L":L,"avgGF":safe_div(gf,n),"avgGA":safe_div(ga,n)}

def _to_float(x):
    try:
        s=str(x).strip()
        if s.endswith("%"): s=s.replace("%","")
        return float(s)
    except: return 0.0

def _extract_xg_from_statistics_block(stat_map: dict):
    if not stat_map: return 0.0
    for k,v in stat_map.items():
        key=(k or "").lower()
        if "xg" in key or ("expected" in key and "goal" in key):
            return _to_float(v)
    return 0.0

# ======================================================
# 🧠 Streamlit Başlangıç
# ======================================================
st.set_page_config(page_title="⚽ Cep Futbol Analiz", layout="wide")
st.title("⚽ Futbol Analiz (Cep/Cloud Sürüm)")

if "live_state" not in st.session_state:
    st.session_state["live_state"]={}

# ======================================================
# 📊 ANALİZ (Excel YOK)
# ======================================================
countries=get_data("countries")
country_names=sorted([c["name"] for c in countries])
country=st.selectbox("Ülke Seç",["Seçiniz"]+country_names)

league_dict={}
if country!="Seçiniz":
    leagues=get_data("leagues",{"country":country,"season":datetime.now().year})
    league_dict={l["league"]["name"]:l["league"]["id"] for l in leagues}
    league=st.selectbox("Lig Seç",["Seçiniz"]+list(league_dict.keys()))
else:
    league="Seçiniz"

team_dict={}
if league!="Seçiniz":
    lid=league_dict[league]
    teams=get_data("teams",{"league":lid,"season":datetime.now().year})
    team_dict={t["team"]["name"]:t["team"]["id"] for t in teams}

col1,col2=st.columns(2)
home_team=col1.selectbox("Ev Takımı",["Seçiniz"]+list(team_dict.keys()))
away_team=col2.selectbox("Deplasman Takımı",["Seçiniz"]+list(team_dict.keys()))

if home_team!="Seçiniz" and away_team!="Seçiniz" and st.button("🔍 Analiz Et"):
    hid=team_dict[home_team]; aid=team_dict[away_team]
    home_fix=get_data("fixtures",{"team":hid,"last":10})
    away_fix=get_data("fixtures",{"team":aid,"last":10})
    H=team_form(home_fix,hid); A=team_form(away_fix,aid)
    lam_home=max(0.2,(H["avgGF"]+A["avgGA"])/2)*1.1
    lam_away=max(0.2,(A["avgGF"]+H["avgGA"])/2)
    M=poisson_matrix(lam_home,lam_away)
    ph,pdraw,pa=wdl_from_poisson(M)
    over25=over25_prob(M)
    btts=btts_prob(M)
    df=pd.DataFrame({"Sonuç":["Ev (1)","Beraberlik (0)","Dep (2)"],
                     "Olasılık (%)":[ph*100,pdraw*100,pa*100]})
    st.subheader("📊 Maç Olasılıkları")
    st.plotly_chart(px.bar(df,x="Sonuç",y="Olasılık (%)",color="Sonuç"),use_container_width=True)
    st.caption("💾 Cloud sürüm: Excel kaydı devre dışı.")

# ======================================================
# ⚡ CANLI ANALİZ (Excel YOK)
# ======================================================
st.markdown("---")
st.header("⚡ Canlı Maç Analizi (xG + Atak + Tehlikeli Atak)")

if st.button("📡 Canlı Maçları Göster"):
    st.session_state["live_state"]["active"]=True

if st.session_state["live_state"].get("active"):
    live_fixtures=get_data("fixtures",{"live":"all"})
    if not live_fixtures:
        st.warning("Şu anda canlı maç yok.")
    else:
        live_matches={f"{f['teams']['home']['name']} vs {f['teams']['away']['name']} ({f['league']['name']})":f["fixture"]["id"] for f in live_fixtures}
        selected=st.selectbox("Canlı Maç Seç",["Seçiniz"]+list(live_matches.keys()))
        if selected!="Seçiniz" and st.button("🔄 Güncelle"):
            fid=live_matches[selected]
            stats=get_data("fixtures/statistics",{"fixture":fid})
            if not stats:
                st.info("Bu maç için istatistik bulunamadı (API gecikmeli olabilir).")
            else:
                stat_data={t["team"]["name"]:{i["type"]:i["value"] for i in t["statistics"]} for t in stats}
                if len(stat_data)<2:
                    st.info("İstatistikler eksik görünüyor.")
                else:
                    hname,aname=list(stat_data.keys())
                    Hs,As=stat_data[hname],stat_data[aname]
                    hxg=_extract_xg_from_statistics_block(Hs)
                    axg=_extract_xg_from_statistics_block(As)
                    pos_diff=_to_float(Hs.get("Ball Possession",0))-_to_float(As.get("Ball Possession",0))
                    shots_diff=_to_float(Hs.get("Total Shots",0))-_to_float(As.get("Total Shots",0))
                    corners_diff=_to_float(Hs.get("Corner Kicks",0))-_to_float(As.get("Corner Kicks",0))
                    attacks_diff=_to_float(Hs.get("Attacks",0))-_to_float(As.get("Attacks",0))
                    danger_diff=_to_float(Hs.get("Dangerous Attacks",0))-_to_float(As.get("Dangerous Attacks",0))
                    xg_diff=hxg-axg
                    score=(shots_diff*2.0)+(pos_diff*0.4)+(corners_diff*1.2)+(attacks_diff*0.5)+(danger_diff*1.0)+(xg_diff*15.0)
                    home_prob=max(0,min(100,50+score/2))
                    away_prob=100-home_prob
                    st.subheader("🎯 Gol Olasılığı")
                    st.markdown(f"**{hname} % {home_prob:.1f}** — **{aname} % {away_prob:.1f}**")

                    comments=[]
                    if danger_diff>5: comments.append("Ev takımı tehlikeli ataklarda üstün, gol ihtimali artıyor.")
                    elif danger_diff<-5: comments.append("Deplasman daha tehlikeli ataklar üretiyor.")
                    if attacks_diff>10: comments.append("Ev takımı hücumda baskın.")
                    elif attacks_diff<-10: comments.append("Deplasman hücum baskısı kuruyor.")
                    if xg_diff>0.3: comments.append("Ev takımının xG değeri yüksek, gol beklenebilir.")
                    elif xg_diff<-0.3: comments.append("Deplasman xG değeri yüksek, gol gelebilir.")
                    if not comments: comments.append("Maç dengede, belirgin üstünlük yok.")
                    st.markdown("### 🧠 Yorum: " + " ".join(comments))
                    st.caption("💾 Cloud sürüm: Excel kaydı devre dışı.")
