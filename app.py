import streamlit as st
import requests
import plotly.express as px
import pandas as pd
import random
from datetime import datetime, timedelta
import re

# --- 1. KONFIGURACJA (BEZPIECZNA) ---
# Kod pobiera klucze WYŁĄCZNIE z bezpiecznego sejfu (lokalnego lub w chmurze)
# Nie ma tu żadnego "except" z jawnym kluczem.
RAPID_API_KEY = st.secrets["RAPID_API_KEY"]
TAG = st.secrets["TAG"]

RAPID_API_HOST = "real-time-amazon-data.p.rapidapi.com"

# --- 2. KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="Złap Okazje", 
    layout="wide", 
    page_icon="🎯",
    initial_sidebar_state="expanded"
)

if 'display_count' not in st.session_state:
    st.session_state.display_count = 12
if 'favorites' not in st.session_state:
    st.session_state.favorites = []

# --- 3. CSS (WYGLĄD) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stHeader"] { background-color: transparent; }
    
    .stApp { background-color: #f4f6f9; }
    .block-container {padding-top: 1rem;}

    /* NAGŁÓWEK */
    .custom-header {
        background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
        padding: 40px; text-align: center; border-bottom: 4px solid #d92027;
        margin-bottom: 30px; color: white; border-radius: 0 0 20px 20px;
        box-shadow: 0 10px 20px rgba(255, 75, 43, 0.2);
    }
    .custom-header h1 {
        font-family: 'Arial Black', sans-serif; font-weight: 900; 
        font-size: 3.5em; margin: 0; text-transform: uppercase;
    }

    /* KARTA GÓRA */
    .card-top {
        background: white; border: 1px solid #ddd; border-bottom: none;
        border-radius: 12px 12px 0 0; padding: 10px;
    }
    .img-container {
        height: 350px; display: flex; align-items: center; justify-content: center;
        padding: 10px;
    }
    .img-container img {
        max-height: 100%; max-width: 100%; object-fit: contain;
        transition: transform 0.3s;
    }
    .img-container img:hover { transform: scale(1.05); }

    .product-title {
        font-weight: 700; font-size: 14px; color: #333; margin-top: 10px;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        cursor: help; display: block;
    }

    /* PRZYCISKI */
    div.stButton > button {
        width: 100%; border-radius: 0; 
        border: 1px solid #ff4b2b; border-left: 1px solid #ddd; border-right: 1px solid #ddd;
        background-color: white; color: #ff4b2b; font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #ff4b2b; color: white; border-color: #ff4b2b;
    }

    /* CENY */
    .card-bottom {
        background: #fafafa; border: 1px solid #ddd; border-top: none;
        border-radius: 0 0 12px 12px; overflow: hidden; margin-bottom: 30px;
    }
    .price-row {
        display: flex; align-items: center; justify-content: space-between;
        padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 13px;
    }
    .best-row { background-color: #e6fffa; border-left: 5px solid #00b894; color: #006652; font-weight: 700; }
    .normal-row { background-color: #fff; border-left: 5px solid transparent; color: #555; }
    .shop-link { text-decoration: none; font-size: 1.4em; color: #333; margin-left: 10px; }
    .shop-link:hover { color: #ff4b2b; }

</style>
""", unsafe_allow_html=True)

# --- 4. LOGIKA ---

def clean_price(price_str):
    """Zamienia tekst '129,99 zł' na liczbę float 129.99"""
    if not price_str or price_str == "Sprawdź": return None
    # Usuwamy wszystko co nie jest cyfrą lub przecinkiem/kropką
    clean = re.sub(r'[^\d,.]', '', price_str)
    # Zamieniamy przecinek na kropkę
    clean = clean.replace(',', '.')
    try:
        return float(clean)
    except:
        return None

def generate_fake_history(current_price_str):
    """Generuje przykładowe dane historyczne do wykresu"""
    price = clean_price(current_price_str)
    if not price: return None
    
    dates = []
    prices = []
    base_date = datetime.now()
    
    # Generujemy 30 dni wstecz
    for i in range(30):
        d = base_date - timedelta(days=30-i)
        dates.append(d.strftime("%Y-%m-%d"))
        # Symulacja wahań +/- 15%
        variation = random.uniform(0.85, 1.15)
        prices.append(round(price * variation, 2))
    
    # Ostatni punkt to dzisiejsza cena
    dates.append(base_date.strftime("%Y-%m-%d"))
    prices.append(price)
    
    return pd.DataFrame({"Data": dates, "Cena (PLN)": prices})

def toggle_favorite(product):
    fav_asins = [p['asin'] for p in st.session_state.favorites]
    if product['asin'] in fav_asins:
        st.session_state.favorites = [p for p in st.session_state.favorites if p['asin'] != product['asin']]
        st.toast("Usunięto ze schowka", icon="🗑️")
    else:
        st.session_state.favorites.append(product)
        st.toast("Dodano do schowka!", icon="❤️")

@st.cache_data
def get_products_rapidapi(query, sort_option):
    url = f"https://{RAPID_API_HOST}/search"
    sort_map = {
        "Trafność": "RELEVANCE",
        "Cena: Od najniższej": "LOWEST_PRICE",
        "Cena: Od najwyższej": "HIGHEST_PRICE"
    }
    api_sort = sort_map.get(sort_option, "RELEVANCE")
    
    querystring = {"query": query, "page": "1", "country": "PL", "sort_by": api_sort}
    headers = {"x-rapidapi-key": RAPID_API_KEY, "x-rapidapi-host": RAPID_API_HOST}

    products = []
    try:
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()
        if "data" in data and "products" in data["data"]:
            items = data["data"]["products"]
        else:
            return []

        for item in items:
            asin = item.get("asin")
            title = item.get("product_title", "Brak tytułu")
            image = item.get("product_photo", "https://placehold.co/400x400?text=Brak")
            price_val = item.get("product_price")
            display_price = price_val if price_val else "Sprawdź"
            link_pl = f"https://www.amazon.pl/dp/{asin}?tag={TAG}"
            
            prices = []
            prices.append({"flag": "🇵🇱", "price_txt": display_price, "link": link_pl, "is_best": True})
            others = [
                {"code": "de", "flag": "🇩🇪", "url": "amazon.de"},
                {"code": "it", "flag": "🇮🇹", "url": "amazon.it"},
                {"code": "es", "flag": "🇪🇸", "url": "amazon.es"},
            ]
            for c in others:
                aff_link = f"https://www.{c['url']}/dp/{asin}?tag={TAG}"
                prices.append({"flag": c['flag'], "price_txt": "Sprawdź", "link": aff_link, "is_best": False})

            products.append({"asin": asin, "title": title, "image": image, "prices": prices})
    except Exception:
        pass 
    return products

# --- 5. INTERFEJS ---

# SIDEBAR
with st.sidebar:
    st.header(f"🧡 Twój Schowek ({len(st.session_state.favorites)})")
    if st.session_state.favorites:
        for fav in st.session_state.favorites:
            with st.container(border=True):
                st.image(fav['image'])
                st.caption(fav['title'][:40])
                if st.button("Usuń", key=f"del_{fav['asin']}"):
                    toggle_favorite(fav)
                    st.rerun()
    else:
        st.info("Pusto. Dodaj coś!")

# GŁÓWNY
st.markdown("""
<div class="custom-header">
    <h1>ZŁAP OKAZJE 🎯</h1>
    <p>Upoluj najlepsze ceny w Europie</p>
</div>
""", unsafe_allow_html=True)

col_s1, col_s2 = st.columns([3, 1])
with col_s1:
    def reset(): st.session_state.display_count = 12
    search = st.text_input("Szukaj produktu:", placeholder="np. Lego...", on_change=reset)
with col_s2:
    sort = st.selectbox("Sortowanie:", ["Trafność", "Cena: Od najniższej", "Cena: Od najwyższej"], on_change=reset)

st.divider()

if search:
    with st.spinner('Szukam...'):
        results = get_products_rapidapi(search, sort)
    
    if results:
        view_res = results[:st.session_state.display_count]
        cols = st.columns(4)
        fav_ids = [p['asin'] for p in st.session_state.favorites]

        for i, prod in enumerate(view_res):
            with cols[i % 4]:
                # GÓRA
                st.markdown(f"""
                <div class="card-top">
                    <div class="img-container"><img src="{prod['image']}"></div>
                    <div class="product-title" title="{prod['title']}">{prod['title']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # PRZYCISK
                is_fav = prod['asin'] in fav_ids
                btn_lbl = "❤️ USUŃ ZE SCHOWKA" if is_fav else "♡ DODAJ DO SCHOWKA"
                if st.button(btn_lbl, key=f"btn_{prod['asin']}", use_container_width=True):
                    toggle_favorite(prod)
                    st.rerun()

                # WYKRES (EXPANDER)
                with st.expander("📈 Analiza Ceny"):
                    # Generujemy historię na podstawie ceny PL
                    pl_price_str = prod['prices'][0]['price_txt']
                    df_history = generate_fake_history(pl_price_str)
                    
                    if df_history is not None:
                        # Rysujemy wykres Plotly
                        fig = px.line(df_history, x="Data", y="Cena (PLN)", markers=True)
                        fig.update_layout(
                            margin=dict(l=0, r=0, t=0, b=0),
                            height=200,
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)"
                        )
                        fig.update_traces(line_color='#ff4b2b')
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    else:
                        st.write("Brak danych historycznych.")

                # DÓŁ (CENY)
                rows = ""
                for p in prod['prices']:
                    cls = "best-row" if p['is_best'] else "normal-row"
                    rows += f'<div class="price-row {cls}"><div><span style="font-size:1.4em;margin-right:5px;">{p["flag"]}</span>{p["price_txt"]}</div><a href="{p["link"]}" target="_blank" class="shop-link">➜</a></div>'
                
                st.markdown(f'<div class="card-bottom">{rows}</div>', unsafe_allow_html=True)

        if st.session_state.display_count < len(results):
            if st.button("ZAŁADUJ WIĘCEJ ⬇", use_container_width=True):
                st.session_state.display_count += 12
                st.rerun()
    else:
        st.warning("Brak wyników.")

st.markdown("<br><div style='text-align:center;color:#ccc;'>ZłapOkazje.top © 2025</div>", unsafe_allow_html=True)