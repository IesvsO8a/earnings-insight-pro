import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta
import streamlit.components.v1 as components
import requests
import numpy as np

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Earnings Insight Pro", layout="wide")

# --- CSS VISUAL ---
st.markdown("""
    <style>
        .bmc-button {
            padding: 5px 10px; 
            border-radius: 5px; 
            background-color: #FFDD00;
            color: #000 !important; 
            text-decoration: none; 
            font-weight: bold;
            display: flex; 
            justify-content: center; 
            border: 1px solid #e0c200;
            margin: 5px 0 10px 0;
        }
        .bmc-button:hover { 
            background-color: #e6c700; 
            text-decoration: none; 
        }
    </style>
""", unsafe_allow_html=True)

# --- RECUPERACIÓN SEGURA DE LA API KEY ---
try:
    API_KEY_FMP = st.secrets["FMP_API_KEY"]
except Exception:
    API_KEY_FMP = None

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    ticker = st.text_input("Símbolo de la Acción (Ticker)", value="").upper()
    dias_analisis = st.slider("Eventos a analizar", 4, 37, 8)
    
    if st.button("Actualizar Análisis"):
        st.cache_data.clear()
    
    st.divider()
    
    st.markdown("### ☕ Apoya el proyecto")
    st.info("Herramienta gratuita. Si la información te es útil, invítame un café para mantener el servidor activo.")
    st.markdown('<a href="https://buymeacoffee.com/iesvso8a" target="_blank" class="bmc-button">☕ Invítame un Café</a>', unsafe_allow_html=True)
    
    st.divider()
    
    if API_KEY_FMP:
        st.caption("Estado: Conectado a FMP (Pro) ✅")
    else:
        st.caption("Estado: Modo Gratuito (Yahoo) ⚠️")

# --- FUNCIONES AUXILIARES ---

def obtener_fechas_fmp(symbol, api_key, limit=50):
    url = f"https://financialmodelingprep.com/api/v3/historical/earning_calendar/{symbol}?limit={limit}&apikey={api_key}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, dict) and "Error Message" in data: return None, "Error API"
        if not data: return None, "No Data"
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        return df, "OK"
    except Exception as e:
        return None, str(e)

def obtener_proximo_earnings(stock_obj):
    """Busca fecha y hora estimada del próximo reporte."""
    fecha_str = "--"
    momento_str = "" 
    
    try:
        dates_df = stock_obj.earnings_dates
        if dates_df is not None:
            future_dates = dates_df[dates_df.index > pd.Timestamp.now().tz_localize('UTC')]
            if not future_dates.empty:
                future_dates = future_dates.sort_index()
                next_event_dt = future_dates.index[0]
                fecha_str = next_event_dt.strftime('%d %b %Y')
                
                hour = next_event_dt.hour
                if 16 <= hour <= 23: momento_str = "🌙 AMC"
                elif 5 <= hour < 16: momento_str = "☀️ BMO"
                else: momento_str = "❓"

        if fecha_str == "--": return "--"
        return f"{fecha_str} {momento_str}"
    except:
        return "--"

# --- LÓGICA PRINCIPAL ---
@st.cache_data(ttl=600, show_spinner=False)
def obtener_datos(symbol, n_eventos, api_key):
    source_used = "Yahoo Finance"
    earnings_data = []
    stock = yf.Ticker(symbol)
    
    # 1. DATOS EN VIVO
    try:
        precio_actual = stock.fast_info['last_price']
        prev_close = stock.fast_info['previous_close']
        variacion_dia = ((precio_actual - prev_close) / prev_close) * 100
        proximo_evento = obtener_proximo_earnings(stock) 
    except:
        precio_actual = 0; variacion_dia = 0; proximo_evento = "--"

    # 2. OBTENER HISTORIAL (Híbrido + EPS)
    use_yahoo = True
    
    # FMP
    if api_key:
        df_fmp, msg = obtener_fechas_fmp(symbol, api_key, limit=n_eventos + 5)
        if df_fmp is not None and not df_fmp.empty:
            use_yahoo = False
            source_used = "FMP Data (Verificado)"
            today = pd.Timestamp.now()
            df_fmp = df_fmp[df_fmp['date'] < today].head(n_eventos)
            
            for _, row in df_fmp.iterrows():
                event_date = row['date'].date()
                time_str = str(row.get('time', '')).lower()
                if 'amc' in time_str or 'after' in time_str:
                    etiqueta = "🌙 AMC"; off_p = 0; off_r = 1
                elif 'bmo' in time_str or 'before' in time_str:
                    etiqueta = "☀️ BMO"; off_p = -1; off_r = 0
                else:
                    etiqueta = "❓ --"; off_p = 0; off_r = 1 
                
                earnings_data.append({
                    'date': event_date, 'etiqueta': etiqueta, 
                    'off_pre': off_p, 'off_react': off_r,
                    'eps_est': row.get('epsEstimated', None), 'eps_act': row.get('eps', None)
                })

    # Yahoo Fallback
    if use_yahoo:
        try:
            earnings_dates = stock.earnings_dates
            if earnings_dates is None: return None, None, None, "Sin datos."
            today = pd.Timestamp.now().tz_localize('UTC')
            past_earnings = earnings_dates[earnings_dates.index < today].head(n_eventos)
            for date_timestamp, row_y in past_earnings.iterrows():
                event_date = date_timestamp.date()
                if date_timestamp.hour >= 15:
                    etiqueta = "🌙 AMC"; off_p = 0; off_r = 1
                else:
                    etiqueta = "☀️ BMO"; off_p = -1; off_r = 0
                
                eps_est = row_y.get('EPS Estimate', None)
                eps_act = row_y.get('Reported EPS', None)
                if pd.isna(eps_est): eps_est = None
                if pd.isna(eps_act): eps_act = None

                earnings_data.append({
                    'date': event_date, 'etiqueta': etiqueta, 
                    'off_pre': off_p, 'off_react': off_r,
                    'eps_est': eps_est, 'eps_act': eps_act
                })
        except Exception:
            return None, None, None, "Error Yahoo."

    # 3. PRECIOS
    data_rows = []
    for evento in earnings_data:
        event_date = evento['date']
        start = event_date - timedelta(days=7)
        end = event_date + timedelta(days=7)
        df_prices = stock.history(start=start, end=end, auto_adjust=False)
        if df_prices.empty: continue

        try:
            loc_idx = df_prices.index.get_indexer([pd.Timestamp(event_date).tz_localize(df_prices.index.dtype.tz)], method='nearest')[0]
            idx_pre = loc_idx + evento['off_pre']
            idx_react = loc_idx + evento['off_react']
            if idx_pre < 0 or idx_react >= len(df_prices): continue

            pre = df_prices.iloc[idx_pre]['Close']
            row_r = df_prices.iloc[idx_react]
            op, hi, lo, cl = row_r['Open'], row_r['High'], row_r['Low'], row_r['Close']
            
            gap = ((op - pre) / pre) * 100
            clo_pct = ((cl - pre) / pre) * 100
            m_hi = hi - pre
            m_lo = lo - pre
            max_raw = m_hi if abs(m_hi) > abs(m_lo) else m_lo
            max_pct = (max_raw / pre) * 100
            
            e_est = evento['eps_est']
            e_act = evento['eps_act']
            sorpresa = None
            if e_est is not None and e_act is not None and e_est != 0:
                sorpresa = ((e_act - e_est) / abs(e_est)) * 100
            
            data_rows.append({
                "Fecha": event_date, "Anuncio": evento['etiqueta'], 
                "EPS Est.": e_est, "EPS Rep.": e_act, "Sorpresa": sorpresa,
                "Pre-Close": pre, "Post-Open": op, "GAP %": gap, 
                "Post-High": hi, "Post-Low": lo, "Post-Close": cl, 
                "CLOSE %": clo_pct, "MAX %": max_pct
            })
        except: continue

    if not data_rows: return (precio_actual, variacion_dia, proximo_evento), None, source_used, "Datos insuficientes."
    return (precio_actual, variacion_dia, proximo_evento), pd.DataFrame(data_rows), source_used, "OK"

# --- VISUALIZACIÓN ---
if not ticker:
    st.title("📊 Earnings Insight | Pro Edition")
    st.markdown("Análisis de reacción de precios post-reporte.")
    st.info("👈 Ingresa un Ticker en el menú lateral y presiona ENTER para comenzar.")
else:
    components.html("""<script>window.parent.document.querySelector('section.main').scrollTo(0, 0);</script>""", height=0, width=0)

    with st.spinner(f'Analizando historial de {ticker}...'):
        datos_live, df, fuente, mensaje = obtener_datos(ticker, dias_analisis, API_KEY_FMP)
        
        if df is not None:
            st.title("📊 Earnings Insight | Pro Edition")
            st.markdown("Análisis de reacción de precios post-reporte.")
            
            if "FMP" in fuente:
                st.caption(f"⚡ Fuente de datos: **{fuente}**")
            else:
                st.caption(f"📡 Fuente de datos: **{fuente}**")
            
            precio, var_dia, prox_fecha = datos_live
            now_ny = pd.Timestamp.now(tz='America/New_York')
            market_open = now_ny.replace(hour=9, minute=30, second=0)
            market_close = now_ny.replace(hour=16, minute=0, second=0)
            emoji_mercado = "☀️" if (0 <= now_ny.dayofweek <= 4 and market_open <= now_ny <= market_close) else "🌙"
            
            # --- ALINEACIÓN SIMÉTRICA (50% - 50%) ---
            # Esto garantiza que la columna derecha (Fecha) esté alineada verticalmente
            # con la caja azul derecha (Max Promedio).
            col_metrica, col_fecha = st.columns(2)
            
            with col_metrica:
                st.metric(
                    label=f"Precio {ticker} {emoji_mercado} (Puede tener retraso)", 
                    value=f"${precio:.2f}", 
                    delta=f"{var_dia:.2f}%"
                )
            
            with col_fecha:
                # Volvemos a la fuente original (Subheader)
                st.markdown(f"**📅 Próximo Reporte (Est.):**")
                st.subheader(f"{prox_fecha}")
                st.caption("*(Puede variar según confirmación oficial)*")
            
            st.divider()
            
            mean_gap = df["GAP %"].abs().mean()
            mean_max = df["MAX %"].abs().mean()
            
            # Mantenemos las columnas 50/50 para las cajas azules también
            c1, c2 = st.columns(2)
            c1.info(f"Gap Promedio (Abs): {mean_gap:.2f}%")
            c2.info(f"Movimiento Max Promedio (Abs): {mean_max:.2f}%")
            
            def color_nums(val):
                color = '#4CAF50' if val > 0 else '#FF5252'
                return f'color: {color}; font-weight: bold'
            
            def color_surprise(val):
                if pd.isna(val): return ''
                color = '#00C853' if val > 0 else '#D50000'
                return f'color: {color}; font-weight: bold'

            altura_tabla = (len(df) + 1) * 35 + 3

            st.dataframe(
                df.style.format({
                    "EPS Est.": "${:.2f}", "EPS Rep.": "${:.2f}", "Sorpresa": "{:.2f}%",
                    "Pre-Close": "${:.2f}", "Post-Open": "${:.2f}", "GAP %": "{:.2f}%",
                    "Post-High": "${:.2f}", "Post-Low": "${:.2f}", "Post-Close": "${:.2f}",
                    "CLOSE %": "{:.2f}%", "MAX %": "{:.2f}%"
                })
                .applymap(color_nums, subset=['GAP %', 'CLOSE %', 'MAX %'])
                .applymap(color_surprise, subset=['Sorpresa']),
                use_container_width=True, hide_index=True, height=altura_tabla 
            )
        elif mensaje: st.warning(f"Aviso: {mensaje}")