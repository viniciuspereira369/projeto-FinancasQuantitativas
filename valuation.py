import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css("style.css")

def get_free_cash_flow(ticker):
    empresa = yf.Ticker(ticker)
    fluxo_de_caixa = empresa.cashflow
    if 'Free Cash Flow' in fluxo_de_caixa.index:
        fcf = fluxo_de_caixa.loc['Free Cash Flow']
        return fcf
    else:
        return None

def estimar_fluxo_de_caixa(fcf_atual, crescimento, periodos):
    estimativas = []
    ultimo_fcf = fcf_atual[-1]  
    for i in range(1, periodos + 1):
        proximo_fcf = ultimo_fcf * (1 + crescimento / 100)
        estimativas.append(proximo_fcf)
        ultimo_fcf = proximo_fcf  

    return estimativas

acoes = ['MGLU3.SA', 'NTCO3.SA', 'PCAR3.SA', 'BHIA3.SA']

wacc = {
    'MGLU3.SA': 0.105, 
    'NTCO3.SA': 0.087, 
    'PCAR3.SA': 0.092, 
    'BHIA3.SA': 0.113
}

acao_selecionada = st.radio("", acoes, index=0)

fcd, pl, ev = st.tabs(["Fluxo de Caixa Descontado", "P/L e Dividend Yield", "EV/EBITDA, ROE e ROA"])

fcf = get_free_cash_flow(acao_selecionada)

if fcf is not None:
    df_fcf = pd.DataFrame(fcf)
    df_fcf = df_fcf.reset_index()
    df_fcf.columns = ['Data', 'Free Cash Flow']
    df_fcf['Data'] = pd.to_datetime(df_fcf['Data']).dt.date  

    def get_historical_data(ticker):
        empresa = yf.Ticker(ticker)
        historico = empresa.history(period="5y")  
        return historico
    

    def get_eps(ticker):
        empresa = yf.Ticker(ticker)
        return empresa.info.get('trailingEps', None)

    def calcular_pl(precos, eps):
        if eps is not None:
            return precos / eps
        else:
            return None

    def calcular_dividend_yield(historico):
        dividendos = historico['Dividends']
        precos = historico['Close']
        dividend_yield = (dividendos / precos) * 100
        return dividend_yield

    def get_financials(ticker):
        empresa = yf.Ticker(ticker)
        info = empresa.info
        return {
            'EV/EBITDA': info.get('enterpriseToEbitda', None),
            'ROE': info.get('returnOnEquity', None),
            'ROA': info.get('returnOnAssets', None)
        }

    historico = get_historical_data(acao_selecionada)
    eps_atual = get_eps(acao_selecionada)


    pl_historico = calcular_pl(historico['Close'], eps_atual)

    dividend_yield_historico = calcular_dividend_yield(historico)


    df_multiplos = pd.DataFrame({
        'Data': historico.index,
        'P/L': pl_historico,
        'Dividend Yield (%)': dividend_yield_historico
    }).dropna()  

    df_fcf = df_fcf.sort_values(by='Data', ascending=True)
    #-----------------------------------------------------------------------------------------------------------------------------------

    with fcd:
        g, per = st.columns(2)

        with per:
            crescimento = st.number_input('Digite a taxa de crescimento perpétuo anual (%)', value=5)
            periodos = st.number_input('Digite o número de períodos a estimar (anos)', min_value=1, value=5)
            wacc = st.slider('Digite a Taxa de Desconto (WACC) (%)', min_value=0.00, max_value=100.00, value=10.55)
        
        estimativas_futuras = estimar_fluxo_de_caixa(df_fcf['Free Cash Flow'].values, crescimento, periodos)

        ultima_data = df_fcf['Data'].max()
        datas_futuras = pd.date_range(ultima_data, periods=periodos + 1, freq='Y')[1:].date  # Gerar datas anuais

        df_estimado = pd.DataFrame({
            'Data': datas_futuras,
            'Free Cash Flow': estimativas_futuras,
            'Tipo': 'Estimado'
        })

        df_fcf['Tipo'] = 'Real'

        df_completo = pd.concat([df_fcf[1:], df_estimado], ignore_index=True)

        with g:
            st.write(f"Projeções de Fluxo de Caixa Livre para {acao_selecionada} com {crescimento}% de crescimento ao ano:")
            st.dataframe(df_completo)

        fig = px.bar(df_completo, x='Data', y='Free Cash Flow', color='Tipo', 
                title=f'Fluxo de Caixa Livre de {acao_selecionada} (com projeções futuras)',
                labels={'Free Cash Flow': 'Free Cash Flow (USD)', 'Data': 'Período'},
                color_discrete_map={'Real': 'blue', 'Estimado': 'orange'})


        def estimar_valor_presente(ticker, crescimento, periodos):
            fluxo_caixa = get_free_cash_flow(ticker)    
            fluxo_caixa = pd.DataFrame(fluxo_caixa)
            fluxo_caixa = fluxo_caixa.reset_index()
            fluxo_caixa.columns = ['Data', 'Free Cash Flow']
            fluxo_caixa['Data'] = pd.to_datetime(fluxo_caixa['Data']).dt.date  

            fluxo_caixa = fluxo_caixa.sort_values(by='Data', ascending=True)

            valor_futuro = estimar_fluxo_de_caixa(fluxo_caixa['Free Cash Flow'].values, crescimento, periodos)
            valor_presente = np.sum([x / ((1 + (wacc/100)) ** (i + 1)) for i, x in enumerate(valor_futuro)])
            return valor_presente

        def estimar_valor_terminal(ticker, crescimento, wacc):
            fluxo_caixa = get_free_cash_flow(ticker)    
            fluxo_caixa = pd.DataFrame(fluxo_caixa)
            fluxo_caixa = fluxo_caixa.reset_index()
            fluxo_caixa.columns = ['Data', 'Free Cash Flow']
            fluxo_caixa['Data'] = pd.to_datetime(fluxo_caixa['Data']).dt.date  

            fluxo_caixa = fluxo_caixa.sort_values(by='Data', ascending=True)

            ultimo_fcf = df_fcf['Free Cash Flow'].values[-1]
            valor_terminal = (ultimo_fcf * (1+crescimento))/(wacc-crescimento)
            return valor_terminal
        valor_terminal = estimar_valor_terminal(acao_selecionada, crescimento, wacc)
        valor_presente = estimar_valor_presente(acao_selecionada, crescimento, periodos)
        st.write(f"Valor Presente Estimado da Empresa {acao_selecionada}: ${valor_presente:,.2f}")
        st.write(f"Valor Presente do Valor do Terminal da Empresa {acao_selecionada}: ${valor_terminal:,.2f}")
        st.write(f"Valor Estimado da Empresa {acao_selecionada}: ${valor_terminal + valor_presente:,.2f}")
        st.plotly_chart(fig, use_container_width=True)
#-------------------------------------------------------------------------------------------------------------------------
        with pl:
            st.write(f"Dados de P/L e Dividend Yield ao longo do tempo para {acao_selecionada}:")
            st.dataframe(df_multiplos)

            fig = px.line(df_multiplos, x='Data', y=['P/L', 'Dividend Yield (%)'], 
                        title=f'Múltiplos Financeiros ao Longo do Tempo - {acao_selecionada}',
                        labels={'value': 'Valor', 'Data': 'Data'}, 
                        color_discrete_map={'P/L': 'blue', 'Dividend Yield (%)': 'orange'})

            st.plotly_chart(fig, use_container_width=True)

            indicadores = get_financials(acao_selecionada)
#----------------------------------------------------------------------------------------------------------------------------------------------
    with ev:
        st.write(f"Indicadores mais recentes para {acao_selecionada}:")
        for indicador, valor in indicadores.items():
            if valor is not None:
                st.write(f"{indicador}: {valor:.2f}")
            else:
                st.write(f"{indicador}: Dados não disponíveis")

        indicadores_vis = pd.DataFrame(list(indicadores.items()), columns=['Indicador', 'Valor']).dropna()

        fig_indicadores = px.bar(indicadores_vis, x='Indicador', y='Valor', 
                                title=f'Indicadores Financeiros para {acao_selecionada}',
                                labels={'Valor': 'Valor', 'Indicador': 'Indicador'},
                                color='Indicador')

        st.plotly_chart(fig_indicadores, use_container_width=True)