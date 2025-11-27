import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta
import streamlit.components.v1 as components

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Earnings Insight Pro", layout="wide")

# --- BARRA LATERAL (INPUTS) ---
with st.sidebar:
    st.header("Configuración")
    ticker = st.text_input("Ticker (Ej. AAPL)", value="").upper()
    dias_analisis = st.slider("Eventos a analizar", 4, 37, 8)
    st.button("Actualizar Análisis") 
    st.divider()
    st.info("El sistema detecta automáticamente si el reporte fue antes (BMO) o después (AMC) del mercado.")

# --- LÓGICA DE DATOS ---
def obtener_datos(symbol, n_eventos):
    try:
        stock = yf.Ticker(symbol)
        
        # 1. PRECIO ACTUAL
        try:
            precio_actual = stock.fast_info['last_price']
            prev_close = stock.fast_info['previous_close']
            variacion_dia = ((precio_actual - prev_close) / prev_close) * 100
        except:
            precio_actual = 0
            variacion_dia = 0
        
        # 2. HISTORIAL DE EARNINGS
        earnings_dates = stock.earnings_dates
        if earnings_dates is None:
            return None, None, "No se encontraron fechas."
            
        today = pd.Timestamp.now().tz_localize('UTC')
        past_earnings = earnings_dates[earnings_dates.index < today].head(n_eventos)
        
        data_rows = []

        for date_timestamp in past_earnings.index:
            event_date = date_timestamp.date()
            event_hour = date_timestamp.hour
            
            # --- DETECCIÓN AUTOMÁTICA BMO/AMC ---
            if event_hour >= 15:
                momento = "AMC"
                etiqueta_momento = "🌙 AMC" 
                offset_pre = 0  
                offset_react = 1 
            else:
                momento = "BMO" 
                etiqueta_momento = "☀️ BMO"
                offset_pre = -1 
                offset_react = 0 
            
            start_data = event_date - timedelta(days=7)
            end_data = event_date + timedelta(days=7)
            
            df_prices = stock.history(start=start_data, end=end_data, auto_adjust=False)
            
            if df_prices.empty:
                continue

            try:
                loc_idx = df_prices.index.get_indexer([pd.Timestamp(event_date).tz_localize(df_prices.index.dtype.tz)], method='nearest')[0]
                
                idx_pre = loc_idx + offset_pre
                idx_react = loc_idx + offset_react
                
                if idx_pre < 0 or idx_react >= len(df_prices):
                    continue

                pre_earnings_row = df_prices.iloc[idx_pre]
                reaction_row = df_prices.iloc[idx_react] 
                
                pre_close = pre_earnings_row['Close']
                
                open_react = reaction_row['Open']
                high_react = reaction_row['High']
                low_react = reaction_row['Low']
                close_react = reaction_row['Close']
                
                # Fórmulas
                gap_pct = ((open_react - pre_close) / pre_close) * 100
                close_pct = ((close_react - pre_close) / pre_close) * 100
                
                move_to_high = high_react - pre_close
                move_to_low = low_react - pre_close
                
                if abs(move_to_high) > abs(move_to_low):
                    max_move_raw = move_to_high
                else:
                    max_move_raw = move_to_low
                    
                max_pct = (max_move_raw / pre_close) * 100
                
                # --- AQUÍ DEFINIMOS LOS NOMBRES DE LAS COLUMNAS ---
                data_rows.append({
                    "Fecha": event_date,
                    "Anuncio": etiqueta_momento,  # Cambiado de "Momento"
                    "Pre-Close": pre_close,
                    "Post-Open": open_react,      # Cambiado de "Open Reacción"
                    "GAP %": gap_pct,
                    "Post-High": high_react,      # Cambiado a Post-High
                    "Post-Low": low_react,        # Cambiado a Post-Low
                    "Post-Close": close_react,    # Cambiado a Post-Close
                    "CLOSE %": close_pct,
                    "MAX %": max_pct
                })
                
            except Exception:
                continue 

        if not data_rows:
            return (precio_actual, variacion_dia), None, "No hay datos suficientes."

        return (precio_actual, variacion_dia), pd.DataFrame(data_rows), "OK"

    except Exception as e:
        return None, None, str(e)

# --- VISUALIZACIÓN PRINCIPAL ---

if not ticker:
    st.title("📊 Earnings Insight | Pro Edition")
    st.markdown("Análisis de reacción de precios post-reporte.")
    st.info("👈 Ingresa un Ticker en el menú lateral y presiona ENTER para comenzar.")

else:
    # Auto-scroll al inicio
    components.html(
        f"""<script>window.parent.document.querySelector('section.main').scrollTo(0, 0);</script>""",
        height=0, width=0
    )

    with st.spinner(f'Analizando historial de {ticker}...'):
        datos_live, df, mensaje = obtener_datos(ticker, dias_analisis)
        
        if datos_live is not None and df is not None:
            
            st.title("📊 Earnings Insight | Pro Edition")
            st.markdown("Análisis de reacción de precios post-reporte.")
            
            precio, var_dia = datos_live
            
            # Emoji Mercado
            now_ny = pd.Timestamp.now(tz='America/New_York')
            market_open = now_ny.replace(hour=9, minute=30, second=0)
            market_close = now_ny.replace(hour=16, minute=0, second=0)
            
            if 0 <= now_ny.dayofweek <= 4 and market_open <= now_ny <= market_close:
                emoji_mercado = "☀️" 
            else:
                emoji_mercado = "🌙" 
            
            st.metric(f"Precio {ticker} {emoji_mercado}", f"${precio:.2f}", f"{var_dia:.2f}%")
            
            # Promedios
            mean_gap = df["GAP %"].abs().mean()
            mean_max = df["MAX %"].abs().mean()
            
            c1, c2 = st.columns(2)
            c1.info(f"Gap Promedio (Abs): {mean_gap:.2f}%")
            c2.info(f"Movimiento Max Promedio (Abs): {mean_max:.2f}%")
            
            st.divider()

            # Estilos
            def color_nums(val):
                color = '#4CAF50' if val > 0 else '#FF5252'
                return f'color: {color}; font-weight: bold'

            altura_tabla = (len(df) + 1) * 35 + 3

            # --- AQUI ESTÁ EL FORMATO (DEBE COINCIDIR EXACTAMENTE CON LOS NOMBRES DE ARRIBA) ---
            st.dataframe(
                df.style.format({
                    "Pre-Close": "${:.2f}",
                    "Post-Open": "${:.2f}",   # Actualizado
                    "GAP %": "{:.2f}%",
                    "Post-High": "${:.2f}",   # Actualizado
                    "Post-Low": "${:.2f}",    # Actualizado
                    "Post-Close": "${:.2f}",  # Actualizado
                    "CLOSE %": "{:.2f}%",
                    "MAX %": "{:.2f}%"
                }).applymap(color_nums, subset=['GAP %', 'CLOSE %', 'MAX %']),
                use_container_width=True,
                hide_index=True,
                height=altura_tabla 
            )
        elif mensaje:
            st.warning(f"Aviso: {mensaje}")