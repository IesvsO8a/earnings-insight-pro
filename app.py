import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta
import streamlit.components.v1 as components
import requests

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Earnings Insight Pro", layout="wide")

# --- CSS VISUAL ---
st.markdown("""
    <style>
        /* ESTILOS DEL ENCABEZADO FIJO (STICKY) */
        div[data-testid="stVerticalBlock"] > div:has(div#sticky-header) {
            position: sticky; top: 2.875rem; background-color: var(--background-color); 
            z-index: 99999; padding: 15px 0; border-bottom: 1px solid rgba(128,128,128,0.2);
            background-image: linear-gradient(var(--background-color), var(--background-color));
        }
        
        /* Separación de la tabla */
        div[data-testid="stDataFrame"] { margin-top: 10px; }
        
        /* ESTILO BOTÓN DONACIÓN (AMARILLO LLAMATIVO) */
        .bmc-button {
            padding: 5px 10px; border-radius: 5px; background-color: #FFDD00;
            color: #000 !important; text-decoration: none; font-weight: bold;
            display: flex; justify-content: center; border: 1px solid #e0c200;
            margin: 5px 0 10px 0;
        }
        .bmc-button:hover { background-color: #e6c700; text-decoration: none; }
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
    
    # Botón de limpieza de memoria (Cache Busting)
    if st.button("Actualizar Análisis"):
        st.cache_data.clear()
    
    st.divider()
    
    # --- SECCIÓN DE APOYO (CAJA AZUL) ---
    st.markdown("### ☕ Apoya el proyecto")
    # st.info crea la caja azul automáticamente
    st.info("Herramienta gratuita. Si la información te es útil, invítame un café para mantener el servidor activo.")
    
    # Botón HTML dentro de la sidebar
    st.markdown('<a href="https://buymeacoffee.com/iesvso8a" target="_blank" class="bmc-button">☕ Invítame un Café</a>', unsafe_allow_html=True)
    
    st.divider()
    
    # Nota técnica discreta
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

# --- LÓGICA PRINCIPAL ---
@st.cache_data(ttl=600, show_spinner=False)
def obtener_datos(symbol, n_eventos, api_key):
    source_used = "Yahoo Finance"
    earnings_data = []
    stock = yf.Ticker(symbol)
    
    # 1. PRECIO ACTUAL
    try:
        precio_actual = stock.fast_info['last_price']
        prev_close = stock.fast_info['previous_close']
        variacion_dia = ((precio_actual - prev_close) / prev_close) * 100
    except:
        precio_actual = 0; variacion_dia = 0

    # 2. OBTENER FECHAS (Híbrido)
    use_yahoo = True
    
    # Intento FMP (Invisible)
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
                
                earnings_data.append({'date': event_date, 'etiqueta': etiqueta, 'off_pre': off_p, 'off_react': off_r})

    # Intento Yahoo (Fallback)
    if use_yahoo:
        try:
            earnings_dates = stock.earnings_dates
            if earnings_dates is None: return None, None, "Sin datos."
            
            today = pd.Timestamp.now().tz_localize('UTC')
            past_earnings = earnings_dates[earnings_dates.index < today].head(n_eventos)
            
            for date_timestamp in past_earnings.index:
                event_date = date_timestamp.date()
                if date_timestamp.hour >= 15:
                    etiqueta = "🌙 AMC"; off_p = 0; off_r = 1
                else:
                    etiqueta = "☀️ BMO"; off_p = -1; off_r = 0
                
                earnings_data.append({'date': event_date, 'etiqueta': etiqueta, 'off_pre': off_p, 'off_react': off_r})
        except Exception:
            return None, None, "Error de conexión con Yahoo."

    # 3. PRECIOS HISTÓRICOS
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
            
            data_rows.append({
                "Fecha": event_date, "Anuncio": evento['etiqueta'], 
                "Pre-Close": pre, "Post-Open": op, "GAP %": gap, 
                "Post-High": hi, "Post-Low": lo, "Post-Close": cl, 
                "CLOSE %": clo_pct, "MAX %": max_pct
            })
        except: continue

    if not data_rows: return (precio_actual, variacion_dia), None, "Datos insuficientes."
    return (precio_actual, variacion_dia), pd.DataFrame(data_rows), source_used

# --- VISUALIZACIÓN ---
if not ticker:
    st.title("📊 Earnings Insight | Pro Edition")
    st.markdown("Análisis de reacción de precios post-reporte.")
    st.info("👈 Ingresa un Ticker en el menú lateral y presiona ENTER para comenzar.")
else:
    components.html("""<script>window.parent.document.querySelector('section.main').scrollTo(0, 0);</script>""", height=0, width=0)

    with st.spinner(f'Analizando historial de {ticker}...'):
        datos_live, df, mensaje = obtener_datos(ticker, dias_analisis, API_KEY_FMP)
        
        if datos_live is not None and df is not None:
            fuente = mensaje 
            with st.container():
                st.markdown('<div id="sticky-header"></div>', unsafe_allow_html=True)
                
                # TÍTULO Y DESCRIPCIÓN RESTAURADA
                st.title("📊 Earnings Insight | Pro Edition")
                st.markdown("Análisis de reacción de precios post-reporte.")
                
                # LEYENDA SUTIL DEL ORIGEN DE DATOS
                if "FMP" in fuente:
                    st.caption(f"⚡ Fuente de datos: **{fuente}**")
                else:
                    st.caption(f"📡 Fuente de datos: **{fuente}**")
                
                precio, var_dia = datos_live
                now_ny = pd.Timestamp.now(tz='America/New_York')
                market_open = now_ny.replace(hour=9, minute=30, second=0)
                market_close = now_ny.replace(hour=16, minute=0, second=0)
                emoji_mercado = "☀️" if (0 <= now_ny.dayofweek <= 4 and market_open <= now_ny <= market_close) else "🌙"
                
                # MÉTRICA DE PRECIO CON ADVERTENCIA DE RETRASO
                st.metric(
                    label=f"Precio {ticker} {emoji_mercado} (Puede tener retraso)", 
                    value=f"${precio:.2f}", 
                    delta=f"{var_dia:.2f}%"
                )
                
                # PROMEDIOS
                mean_gap = df["GAP %"].abs().mean()
                mean_max = df["MAX %"].abs().mean()
                c1, c2 = st.columns(2)
                c1.info(f"Gap Promedio (Abs): {mean_gap:.2f}%")
                c2.info(f"Movimiento Max Promedio (Abs): {mean_max:.2f}%")
            
            # TABLA
            def color_nums(val):
                color = '#4CAF50' if val > 0 else '#FF5252'
                return f'color: {color}; font-weight: bold'

            altura_tabla = (len(df) + 1) * 35 + 3

            st.dataframe(
                df.style.format({
                    "Pre-Close": "${:.2f}", "Post-Open": "${:.2f}", "GAP %": "{:.2f}%",
                    "Post-High": "${:.2f}", "Post-Low": "${:.2f}", "Post-Close": "${:.2f}",
                    "CLOSE %": "{:.2f}%", "MAX %": "{:.2f}%"
                }).applymap(color_nums, subset=['GAP %', 'CLOSE %', 'MAX %']),
                use_container_width=True, hide_index=True, height=altura_tabla 
            )
        elif mensaje: st.warning(f"Aviso: {mensaje}")