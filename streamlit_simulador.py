# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import plotly.express as px
from datetime import datetime
from pathlib import Path
import pytz
import io

st.set_page_config(page_title="Simulador de Separação de Produtos", layout="wide")

col_titulo, col_botao, col_download, col_vazio = st.columns([5, 2, 2, 10])

with col_titulo:
    st.title("🧪 Simulador de Separação de Produtos")

with col_botao:
    iniciar = st.button("▶️ Iniciar Simulação", use_container_width=True)

with col_download:
    baixar = st.download_button("⬇️ Baixar Relatório", data=None, file_name="Relatorio_Simulacao.xlsx", disabled=True, use_container_width=True)

# Layout colunas principais
col_esq, col_dir = st.columns([2, 2])

# Entrada de parâmetros (lado esquerdo)
with col_esq:
    tempo_produto = st.number_input("⏱️ Tempo médio por produto (s)", value=20.0, step=1.0, format="%.2f")
    tempo_deslocamento = st.number_input("🚚 Tempo entre estações (s)", value=5.0, step=1.0, format="%.2f")
    capacidade_estacao = st.number_input("📦 Capacidade máxima de caixas simultâneas por estação", value=10, min_value=1)
    pessoas_por_estacao = st.number_input("👷‍♂️ Número de pessoas por estação", value=1.0, min_value=0.01, step=0.1, format="%.2f")
    tempo_adicional_caixa = st.number_input("➕ Tempo adicional por caixa (s)", value=0.0, step=1.0, format="%.2f")
    novo_arquivo = st.file_uploader("📂 Arquivo para Simulação", type=["xlsx"], key="upload_simulacao")

# Salva o arquivo no estado, se for novo upload
if novo_arquivo is not None:
    st.session_state.arquivo_atual = novo_arquivo

# Usa o arquivo do estado, se disponível
uploaded_file = st.session_state.get("arquivo_atual", None)

# Função para formatar tempo
def formatar_tempo(segundos):
    if segundos < 60:
        return f"{int(round(segundos))} segundos"
    dias = int(segundos // 86400)
    segundos %= 86400
    horas = int(segundos // 3600)
    segundos %= 3600
    minutos = int(segundos // 60)
    segundos = int(round(segundos % 60))
    partes = []
    if dias > 0: partes.append(f"{dias} {'dia' if dias == 1 else 'dias'}")
    if horas > 0: partes.append(f"{horas} {'hora' if horas == 1 else 'horas'}")
    if minutos > 0: partes.append(f"{minutos} {'minuto' if minutos == 1 else 'minutos'}")
    if segundos > 0: partes.append(f"{segundos} {'segundo' if segundos == 1 else 'segundos'}")
    return " e ".join(partes)

# Inicializa session_state
if "simulacoes_salvas" not in st.session_state:
    st.session_state.simulacoes_salvas = {}
if "ultima_simulacao" not in st.session_state:
    st.session_state.ultima_simulacao = {}
if "ordem_simulacoes" not in st.session_state:
    st.session_state.ordem_simulacoes = []

# Upload para comparação externo
st.markdown("---")
st.subheader("📁 Comparação com Outro Arquivo Excel (Opcional)")
uploaded_comp = st.file_uploader("📁 Arquivo para Comparação", type=["xlsx"], key="upload_comparacao")

# Botão de simulação e opções
with col_esq:
    ver_graficos = st.checkbox("📊 Ver gráficos e dashboards", value=True, disabled=True)
    comparar_simulacoes = st.checkbox("🔁 Comparar com simulações anteriores ou Excel", value=True,  disabled=True)

# Início da simulação
if uploaded_file is not None and iniciar:
    try:
        df = pd.read_excel(uploaded_file)
        df = df.sort_values(by=["ID_Pacote", "ID_Caixas"])
        caixas = df["ID_Caixas"].unique()

        estimativas, tempo_caixas = [], {}
        disponibilidade_estacao = defaultdict(list)
        tempo_por_estacao = defaultdict(float)
        gargalo_ocorrido = False
        tempo_gargalo = None
        tempo_total_simulacao = 0

        for caixa in caixas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            total_produtos = caixa_df["Contagem de Produto"].sum()
            num_estacoes = caixa_df["Estação"].nunique()
            tempo_estimado = (total_produtos * tempo_produto) / pessoas_por_estacao + (num_estacoes * tempo_deslocamento) + tempo_adicional_caixa
            estimativas.append((caixa, tempo_estimado))

        caixas_ordenadas = [cx for cx, _ in sorted(estimativas, key=lambda x: x[1])]

        for caixa in caixas_ordenadas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            tempo_inicio_caixa = 0
            tempos_finais = []

            for _, linha in caixa_df.iterrows():
                estacao = linha["Estação"]
                contagem = linha["Contagem de Produto"]
                duracao = (contagem * tempo_produto) / pessoas_por_estacao + tempo_deslocamento

                if not disponibilidade_estacao[estacao]:
                    disponibilidade_estacao[estacao] = [0.0] * int(max(1, pessoas_por_estacao))

                idx_pessoa_livre = disponibilidade_estacao[estacao].index(min(disponibilidade_estacao[estacao]))
                inicio = max(disponibilidade_estacao[estacao][idx_pessoa_livre], tempo_inicio_caixa)
                fim = inicio + duracao

                if len(disponibilidade_estacao[estacao]) >= capacidade_estacao and not gargalo_ocorrido and inicio > 0:
                    gargalo_ocorrido = True
                    tempo_gargalo = inicio

                disponibilidade_estacao[estacao][idx_pessoa_livre] = fim
                tempo_por_estacao[estacao] += duracao
                tempos_finais.append(fim)

            fim_caixa = max(tempos_finais) + tempo_adicional_caixa if tempos_finais else 0
            tempo_caixas[caixa] = fim_caixa - tempo_inicio_caixa
            tempo_total_simulacao = max(tempo_total_simulacao, fim_caixa)

        # Guarda dados na sessão
        fuso_brasil = pytz.timezone("America/Sao_Paulo")
        data_hora = datetime.now(fuso_brasil).strftime("%Y-%m-%d_%Hh%Mmin")
        nome_base = Path(uploaded_file.name).stem
        id_simulacao = f"{nome_base}_{data_hora}"

        st.session_state.ultima_simulacao = {
            "tempo_total": tempo_total_simulacao,
            "tempo_por_estacao": tempo_por_estacao,
            "gargalo": tempo_gargalo,
            "total_caixas": len(caixas),
            "tempo_caixas": tempo_caixas,
            "id": id_simulacao,
            "df_simulacao": df  # salva o dataframe para relatórios
        }

        st.session_state.simulacoes_salvas[id_simulacao] = st.session_state.ultima_simulacao
        st.session_state.ordem_simulacoes.append(id_simulacao)

        if len(st.session_state.simulacoes_salvas) > 5:
            ids = sorted(st.session_state.simulacoes_salvas)[-5:]
            st.session_state.simulacoes_salvas = {k: st.session_state.simulacoes_salvas[k] for k in ids}
            st.session_state.ordem_simulacoes = ids

        #st.success(f"✅ Simulação salva como ID: {id_simulacao}")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

    # Exibição do último resultado e relatórios no lado direito
    with col_dir:
        if "ultima_simulacao" in st.session_state and st.session_state.ultima_simulacao:
            sim = st.session_state.ultima_simulacao
            tempo_total = sim["tempo_total"]
            gargalo = sim["gargalo"]
            tempo_por_estacao = sim["tempo_por_estacao"]
            caixas = sim["total_caixas"]
            tempo_caixas = sim["tempo_caixas"]
            df_sim = sim.get("df_simulacao", pd.DataFrame())
        
    
            # Relatório detalhado por caixa com tempo
            if tempo_caixas:
                df_relatorio_caixas = pd.DataFrame([
                    {"Caixa": cx, "Tempo total da caixa (s)": t, "Tempo formatado": formatar_tempo(t)}
                    for cx, t in tempo_caixas.items()
                ])
                df_relatorio_caixas = df_relatorio_caixas.sort_values(by="Tempo total da caixa (s)", ascending=False)
                st.markdown("### 🗂️ Relatório detalhado por Caixa")
                st.dataframe(df_relatorio_caixas)
        
            # Relatório resumido por loja (somando tempos das caixas de cada loja)
            if not df_sim.empty and "ID_Loja" in df_sim.columns:
                # cria df caixa->loja
                df_caixas_loja = df_sim[["ID_Caixas", "ID_Loja"]].drop_duplicates()
                # junta tempo por caixa
                df_caixas_loja["Tempo_caixa"] = df_caixas_loja["ID_Caixas"].map(tempo_caixas)
                # agrupa por loja
                df_relatorio_loja = df_caixas_loja.groupby("ID_Loja").agg(
                    Total_Caixas=("ID_Caixas", "count"),
                    Tempo_Total_Segundos=("Tempo_caixa", "sum")
                ).reset_index()
                df_relatorio_loja["Tempo Formatado"] = df_relatorio_loja["Tempo_Total_Segundos"].apply(formatar_tempo)
                st.markdown("### 🏬 Relatório resumido por Loja")
                st.dataframe(df_relatorio_loja.sort_values(by="Tempo_Total_Segundos", ascending=False))
                
    with col_esq:        
            st.markdown("---")
            st.subheader("📊 Resultados da Simulação")
            st.write(f"🔚 **Tempo total para separar todas as caixas:** {formatar_tempo(tempo_total)}")
            st.write(f"📦 **Total de caixas simuladas:** {caixas}")
            st.write(f"🧱 **Tempo até o primeiro gargalo:** {formatar_tempo(gargalo) if gargalo else 'Nenhum gargalo'}")

        # Sugestão layout otimizado (já no relatório principal)
    if 'df_comp' in locals() and not df_comp.empty:
        st.markdown("---")
        st.subheader("🧠 Sugestão de Layout Otimizado")
        df_estacoes = pd.DataFrame([
            {"Estação": est, "Tempo Total (s)": tempo} for est, tempo in tempo_por_estacao.items()
        ])
        tempo_medio = df_estacoes["Tempo Total (s)"].mean()
        limiar = 1.5 * tempo_medio
        estacoes_sobrec = df_estacoes[df_estacoes["Tempo Total (s)"] > limiar]

        if not estacoes_sobrec.empty:
            st.warning("⚠️ Estações sobrecarregadas detectadas! Sugere-se redistribuir produtos para:")
            st.dataframe(estacoes_sobrec.assign(Sugestao="Redistribuir para estações abaixo da média."))
        else:
            st.success("🚀 Nenhuma estação sobrecarregada detectada.")

# Comparação com simulações anteriores ou arquivo externo
if comparar_simulacoes:
    st.markdown("---")

    ids = st.session_state.ordem_simulacoes[-2:]  # últimas 2 simulações
    if len(ids) < 2 and uploaded_comp is None:
        st.info("Nenhuma comparação possível: faça pelo menos duas simulações ou envie um arquivo para comparação.")
    else:
        # Comparação com arquivo externo
        if uploaded_comp is not None:
            try:
                df_comp_ext = pd.read_excel(uploaded_comp)
                df_comp_ext = df_comp_ext.sort_values(by=["ID_Pacote", "ID_Caixas"])
                caixas_ext = df_comp_ext["ID_Caixas"].unique()
                tempo_estacao_ext = defaultdict(float)

                for caixa in caixas_ext:
                    caixa_df = df_comp_ext[df_comp_ext["ID_Caixas"] == caixa]
                    for _, linha in caixa_df.iterrows():
                        estacao = linha["Estação"]
                        contagem = linha["Contagem de Produto"]
                        tempo = (contagem * tempo_produto) / pessoas_por_estacao + tempo_deslocamento
                        tempo_estacao_ext[estacao] += tempo

                df2 = pd.DataFrame([
                    {"Estação": est, "Tempo (s)": tempo, "Simulação": "Arquivo Comparado"}
                    for est, tempo in tempo_estacao_ext.items()
                ])
                sim2_label = "Arquivo Comparado"
                tempo2 = df2["Tempo (s)"].max()
                caixas2 = len(caixas_ext)

                id1 = ids[-1] if ids else None
                sim1 = st.session_state.simulacoes_salvas[id1] if id1 else None

            except Exception as e:
                st.error(f"Erro ao processar arquivo de comparação: {e}")
                df2 = pd.DataFrame()
                tempo2 = 0
                caixas2 = 0
                sim2_label = "Erro"
                sim1 = None
        else:
            # Comparação entre últimas 2 simulações salvas
            id1, id2 = ids[-2], ids[-1]
            sim1 = st.session_state.simulacoes_salvas[id1]
            sim2 = st.session_state.simulacoes_salvas[id2]
            tempo1 = sim1["tempo_total"]
            tempo2 = sim2["tempo_total"]
            caixas1 = sim1["total_caixas"]
            caixas2 = sim2["total_caixas"]
            sim2_label = id2

            df1 = pd.DataFrame([
                {"Estação": est, "Tempo (s)": tempo, "Simulação": id1}
                for est, tempo in sim1["tempo_por_estacao"].items()
            ])
            df2 = pd.DataFrame([
                {"Estação": est, "Tempo (s)": tempo, "Simulação": id2}
                for est, tempo in sim2["tempo_por_estacao"].items()
            ])

        if sim1 is not None and not df2.empty:
            if 'tempo1' not in locals():
                tempo1 = sim1["tempo_total"]
            if 'caixas1' not in locals():
                caixas1 = sim1["total_caixas"]

            df1 = pd.DataFrame([
                {"Estação": est, "Tempo (s)": tempo, "Simulação": sim1["id"]}
                for est, tempo in sim1["tempo_por_estacao"].items()
            ])

            df_comp = pd.concat([df1, df2], ignore_index=True)

            st.markdown("### 📊 Comparativo de Tempo por Estação")
            fig_comp = px.bar(df_comp, x="Estação", y="Tempo (s)", color="Simulação", barmode="group")
            st.plotly_chart(fig_comp, use_container_width=True)

            delta_tempo = tempo2 - tempo1
            abs_pct = abs(delta_tempo / tempo1 * 100) if tempo1 else 0
            direcao = "melhorou" if delta_tempo < 0 else "aumentou"

            caixas_diferenca = caixas2 - caixas1
            caixas_pct = (caixas_diferenca / caixas1 * 100) if caixas1 else 0

            tempo_formatado = formatar_tempo(abs(delta_tempo))
            # Força a lógica onde diminuir o tempo é positivo (verde), aumentar é negativo (vermelho)
            st.metric(
                "Delta de Tempo Total",
                f"{tempo_formatado}",
                f"{delta_tempo:+.0f}s ({abs_pct:.1f}% {direcao})",
                delta_color="inverse"  # menor é verde, maior é vermelho
            )
            
            st.write(f"📦 **Caixas Base:** {caixas1} | **Comparada:** {caixas2} | Δ {caixas_diferenca:+} caixas ({caixas_pct:+.1f}%)")

            

elif uploaded_comp is not None:
    st.warning("⚠️ Para comparar corretamente, primeiro clique em '▶️ Iniciar Simulação' com o novo arquivo carregado.")


# Gera relatório somente se houver resultados
if "ultima_simulacao" in st.session_state and st.session_state.ultima_simulacao:

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        
        sim = st.session_state.ultima_simulacao
        df_sim = sim.get("df_simulacao", pd.DataFrame())
        tempo_total = sim["tempo_total"]
        gargalo = sim["gargalo"]
        total_caixas = sim["total_caixas"]
        
        # Primeira guia: Resumo
        resumo = [
            ["Parâmetros Utilizados", ""],
            ["Tempo por produto (s)", tempo_produto],
            ["Tempo entre estações (s)", tempo_deslocamento],
            ["Capacidade máxima por estação", capacidade_estacao],
            ["Pessoas por estação", pessoas_por_estacao],
            ["Tempo adicional por caixa (s)", tempo_adicional_caixa],
            ["", ""],
            ["Resultados da Simulação", ""],
            ["Tempo total para separar todas as caixas", formatar_tempo(tempo_total)],
            ["Total de caixas simuladas", total_caixas],
            ["Tempo até o primeiro gargalo", formatar_tempo(gargalo) if gargalo else "Nenhum gargalo"]
        ]
        
        # Se tiver comparação gerada
        if 'delta_tempo' in locals():
            resumo.extend([
                ["", ""],
                ["Comparativo com Simulação Anterior ou Arquivo Externo", ""],
                ["Delta de Tempo Total", formatar_tempo(abs(delta_tempo))],
                ["Variação (s)", f"{delta_tempo:+.0f} s"],
                ["Variação (%)", f"{abs_pct:.1f} % {direcao}"],
                ["Caixas Base", caixas1],
                ["Caixas Comparada", caixas2],
                ["Δ Caixas", f"{caixas_diferenca:+} ({caixas_pct:+.1f}%)"]
            ])
        
        df_resumo = pd.DataFrame(resumo, columns=["Descrição", "Valor"])
        df_resumo.to_excel(writer, sheet_name="Resumo", index=False)

        # Segunda guia: Relatório por Caixa
        if "tempo_caixas" in sim and sim["tempo_caixas"]:
            df_caixas = pd.DataFrame([
                {"Caixa": cx, "Tempo total da caixa (s)": t, "Tempo formatado": formatar_tempo(t)}
                for cx, t in sim["tempo_caixas"].items()
            ])
            df_caixas.to_excel(writer, sheet_name="Por Caixa", index=False)

        # Terceira guia: Relatório por Loja
        if not df_sim.empty and "ID_Loja" in df_sim.columns:
            df_caixas_loja = df_sim[["ID_Caixas", "ID_Loja"]].drop_duplicates()
            df_caixas_loja["Tempo_caixa"] = df_caixas_loja["ID_Caixas"].map(sim["tempo_caixas"])
            df_loja = df_caixas_loja.groupby("ID_Loja").agg(
                Total_Caixas=("ID_Caixas", "count"),
                Tempo_Total_Segundos=("Tempo_caixa", "sum")
            ).reset_index()
            df_loja["Tempo formatado"] = df_loja["Tempo_Total_Segundos"].apply(formatar_tempo)
            df_loja.to_excel(writer, sheet_name="Por Loja", index=False)

        # Quarta guia: Comparação por Estação, se houver
        if 'df_comp' in locals() and not df_comp.empty:
            df_comp.to_excel(writer, sheet_name="Comparação por Estação", index=False)

    relatorio_final = output.getvalue()

    # Botão de download agora com dados reais
    with col_download:
        st.download_button(
            "⬇️ Baixar Relatório",
            data=relatorio_final,
            file_name="Relatorio_Simulacao.xlsx",
            use_container_width=True
        )

