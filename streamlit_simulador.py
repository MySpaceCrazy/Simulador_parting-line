# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import plotly.express as px
from datetime import datetime
from pathlib import Path
import pytz

st.set_page_config(page_title="Simulador de Separação de Produtos", layout="wide")

# --- Cabeçalho com título e botão iniciar ---
col_titulo, col_botao, col_vazio = st.columns([5, 2, 2])

with col_titulo:
    st.title("🧪 Simulador de Separação de Produtos")

with col_botao:
    iniciar = st.button("▶️ Iniciar Simulação", use_container_width=True)

# --- Layout principal: colunas esquerda e direita ---
col_esq, col_dir = st.columns([2, 2])

# --- Entrada de parâmetros no lado esquerdo ---
with col_esq:
    tempo_produto = st.number_input("⏱️ Tempo médio por produto (s)", value=20.0, step=1.0, format="%.2f")
    tempo_deslocamento = st.number_input("🚚 Tempo entre estações (s)", value=5.0, step=1.0, format="%.2f")
    capacidade_estacao = st.number_input("📦 Capacidade máxima de caixas simultâneas por estação", value=10, min_value=1)
    pessoas_por_estacao = st.number_input("👷‍♂️ Número de pessoas por estação", value=1.0, min_value=0.01, step=0.1, format="%.2f")
    tempo_adicional_caixa = st.number_input("➕ Tempo adicional por caixa (s)", value=0.0, step=1.0, format="%.2f")
    novo_arquivo = st.file_uploader("📂 Arquivo para Simulação", type=["xlsx"], key="upload_simulacao")

# --- Salva os parâmetros no session_state para uso no relatório ---
st.session_state.tempo_produto = tempo_produto
st.session_state.tempo_deslocamento = tempo_deslocamento
st.session_state.capacidade_estacao = capacidade_estacao
st.session_state.pessoas_por_estacao = pessoas_por_estacao
st.session_state.tempo_adicional_caixa = tempo_adicional_caixa

# --- Salva arquivo no session_state, se for novo upload ---
if novo_arquivo is not None:
    st.session_state.arquivo_atual = novo_arquivo

# --- Usa arquivo salvo na sessão ---
uploaded_file = st.session_state.get("arquivo_atual", None)

# --- Função para formatar tempo ---
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
    if dias > 0:
        partes.append(f"{dias} {'dia' if dias == 1 else 'dias'}")
    if horas > 0:
        partes.append(f"{horas} {'hora' if horas == 1 else 'horas'}")
    if minutos > 0:
        partes.append(f"{minutos} {'minuto' if minutos == 1 else 'minutos'}")
    if segundos > 0:
        partes.append(f"{segundos} {'segundo' if segundos == 1 else 'segundos'}")
    return " e ".join(partes)

# --- Inicializa session_state para simulações ---
if "simulacoes_salvas" not in st.session_state:
    st.session_state.simulacoes_salvas = {}
if "ultima_simulacao" not in st.session_state:
    st.session_state.ultima_simulacao = {}
if "ordem_simulacoes" not in st.session_state:
    st.session_state.ordem_simulacoes = []

# --- Upload para comparação externa ---
st.markdown("---")
st.subheader("📁 Comparação com Outro Arquivo Excel (Opcional)")
uploaded_comp = st.file_uploader("📁 Arquivo para Comparação", type=["xlsx"], key="upload_comparacao")

# --- Botões e opções adicionais no lado esquerdo ---
with col_esq:
    ver_graficos = st.checkbox("📊 Ver gráficos e dashboards", value=True, disabled=True)
    comparar_simulacoes = st.checkbox("🔁 Comparar com simulações anteriores ou Excel", value=True, disabled=True)

# --- Inicia a simulação após clicar no botão e ter arquivo ---
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

        # --- Estima tempo total para ordenar caixas ---
        for caixa in caixas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            total_produtos = caixa_df["Contagem de Produto"].sum()
            num_estacoes = caixa_df["Estação"].nunique()
            tempo_estimado = (total_produtos * tempo_produto) / pessoas_por_estacao + (num_estacoes * tempo_deslocamento) + tempo_adicional_caixa
            estimativas.append((caixa, tempo_estimado))

        caixas_ordenadas = [cx for cx, _ in sorted(estimativas, key=lambda x: x[1])]

        # --- Calcula tempos reais respeitando capacidade e gargalos ---
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

        # --- Salva dados da simulação no session_state ---
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

        # Mantém no máximo 5 simulações salvas
        if len(st.session_state.simulacoes_salvas) > 5:
            ids = sorted(st.session_state.simulacoes_salvas)[-5:]
            st.session_state.simulacoes_salvas = {k: st.session_state.simulacoes_salvas[k] for k in ids}
            st.session_state.ordem_simulacoes = ids

        #st.success(f"✅ Simulação salva como ID: {id_simulacao}")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

    # --- Exibição do último resultado e relatórios no lado direito ---
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

            # Resultados resumidos
            st.markdown("---")
            st.subheader("📊 Resultados da Simulação")
            st.write(f"🔚 **Tempo total para separar todas as caixas:** {formatar_tempo(tempo_total)}")
            st.write(f"📦 **Total de caixas simuladas:** {caixas}")
            st.write(f"🧱 **Tempo até o primeiro gargalo:** {formatar_tempo(gargalo) if gargalo else 'Nenhum gargalo'}")

            # --- Botão para baixar relatório Excel ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:

                # Monta resumo de parâmetros e resultados
                resumo = {
                    "Parâmetros": [
                        f"Tempo médio por produto: {st.session_state.tempo_produto}s",
                        f"Tempo entre estações: {st.session_state.tempo_deslocamento}s",
                        f"Capacidade por estação: {st.session_state.capacidade_estacao}",
                        f"Pessoas por estação: {st.session_state.pessoas_por_estacao}",
                        f"Tempo adicional por caixa: {st.session_state.tempo_adicional_caixa}s"
                    ],
                    "Resultados": [
                        f"Tempo total simulação: {formatar_tempo(tempo_total)}",
                        f"Total de caixas: {caixas}",
                        f"Tempo até primeiro gargalo: {formatar_tempo(gargalo) if gargalo else 'Nenhum gargalo'}"
                    ]
                }

                df_resumo = pd.DataFrame({
                    "Descrição": ["Parâmetros"] + resumo["Parâmetros"] + ["", "Resultados"] + resumo["Resultados"]
                })
                df_resumo.to_excel(writer, sheet_name="Resumo_Simulação", index=False)

                # Planilha por caixa
                if sim.get("tempo_caixas"):
                    df_caixas = pd.DataFrame([
                        {"Caixa": cx, "Tempo Total (s)": t, "Tempo Formatado": formatar_tempo(t)}
                        for cx, t in sim["tempo_caixas"].items()
                    ])
                    df_caixas.to_excel(writer, sheet_name="Por_Caixa", index=False)

                # Planilha por loja
                if not df_sim.empty and "ID_Loja" in df_sim.columns:
                    df_lojas = df_sim[["ID_Caixas", "ID_Loja"]].drop_duplicates()
                    df_lojas["Tempo_Caixa"] = df_lojas["ID_Caixas"].map(sim["tempo_caixas"])
                    df_lojas_resumo = df_lojas.groupby("ID_Loja").agg(
                        Total_Caixas=("ID_Caixas", "count"),
                        Tempo_Total_Segundos=("Tempo_Caixa", "sum")
                    ).reset_index()
                    df_lojas_resumo["Tempo Formatado"] = df_lojas_resumo["Tempo_Total_Segundos"].apply(formatar_tempo)
                    df_lojas_resumo.to_excel(writer, sheet_name="Por_Loja", index=False)

                # Planilha de comparação por estação (se existir)
                if "df_comp" in locals() and not df_comp.empty:
                    df_comp.to_excel(writer, sheet_name="Comparativo", index=False)

            relatorio_bytes = buffer.getvalue()

            st.download_button(
                label="📥 Baixar Relatórios",
                data=relatorio_bytes,
                file_name=f"Relatorio_Simulacao_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # --- Sugestão layout otimizado ---
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

# --- Comparação com simulações anteriores ou arquivo externo ---
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
            sim1_label = id1
            sim2_label = id2

            df1 = pd.DataFrame([
                {"Estação": est, "Tempo (s)": tempo}
                for est, tempo in sim1["tempo_por_estacao"].items()
            ])
            df2 = pd.DataFrame([
                {"Estação": est, "Tempo (s)": tempo}
                for est, tempo in sim2["tempo_por_estacao"].items()
            ])

        # Junta os dados para gráfico
        if 'df1' in locals() and not df1.empty and not df2.empty:
            df1["Simulação"] = sim1_label
            df2["Simulação"] = sim2_label
            df_comp = pd.concat([df1, df2])

            fig = px.bar(df_comp, x="Estação", y="Tempo (s)", color="Simulação",
                         barmode="group", title="⏳ Comparativo de Tempo por Estação")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown(f"Tempo total simulação 1 ({sim1_label}): {formatar_tempo(tempo1)}")
            st.markdown(f"Tempo total simulação 2 ({sim2_label}): {formatar_tempo(tempo2)}")
            st.markdown(f"Caixas simulação 1: {caixas1}")
            st.markdown(f"Caixas simulação 2: {caixas2}")

        else:
            st.info("Não há dados suficientes para gerar comparativo.")

else:
    if not iniciar:
        st.info("Faça o upload do arquivo e clique em '▶️ Iniciar Simulação' para começar.")

