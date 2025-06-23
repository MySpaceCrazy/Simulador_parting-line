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

st.session_state.tempo_produto = tempo_produto
st.session_state.tempo_deslocamento = tempo_deslocamento
st.session_state.capacidade_estacao = capacidade_estacao
st.session_state.pessoas_por_estacao = pessoas_por_estacao
st.session_state.tempo_adicional_caixa = tempo_adicional_caixa

if novo_arquivo is not None:
    st.session_state.arquivo_atual = novo_arquivo

uploaded_file = st.session_state.get("arquivo_atual", None)





# --- Inicializa session_state para simulações ---
if "simulacoes_salvas" not in st.session_state:
    st.session_state.simulacoes_salvas = {}
if "ultima_simulacao" not in st.session_state:
    st.session_state.ultima_simulacao = {}
if "ordem_simulacoes" not in st.session_state:
    st.session_state.ordem_simulacoes = []

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

# --- Botões e opções adicionais no lado esquerdo ---
st.markdown("---")
st.subheader("📁 Comparação com Outro Arquivo Excel (Opcional)")
uploaded_comp = st.file_uploader("📁 Arquivo para Comparação", type=["xlsx"], key="upload_comparacao")

ver_graficos = st.checkbox("📊 Ver gráficos e dashboards", value=True, disabled=True)
comparar_simulacoes = st.checkbox("🔁 Comparar com simulações anteriores ou Excel", value=True, disabled=True)






# --- Inicia Simulação ---
if uploaded_file and iniciar:
    try:
        df = pd.read_excel(uploaded_file)
        df = df.sort_values(by=["ID_Pacote", "ID_Caixas"])
        caixas = df["ID_Caixas"].unique()

        tempo_caixas, tempo_por_estacao = {}, defaultdict(float)
        disponibilidade_estacao = defaultdict(list)
        gargalo_ocorrido, tempo_gargalo = False, None
        tempo_total_simulacao = 0

        for caixa in caixas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            total_produtos = caixa_df["Contagem de Produto"].sum()
            num_estacoes = caixa_df["Estação"].nunique()

            tempo_estimado = (total_produtos * tempo_produto) / pessoas_por_estacao + (num_estacoes * tempo_deslocamento) + tempo_adicional_caixa

            tempos_finais = []
            for _, linha in caixa_df.iterrows():
                estacao, contagem = linha["Estação"], linha["Contagem de Produto"]
                duracao = (contagem * tempo_produto) / pessoas_por_estacao + tempo_deslocamento

                if not disponibilidade_estacao[estacao]:
                    disponibilidade_estacao[estacao] = [0.0] * int(max(1, pessoas_por_estacao))

                idx_livre = disponibilidade_estacao[estacao].index(min(disponibilidade_estacao[estacao]))
                inicio = max(disponibilidade_estacao[estacao][idx_livre], max(tempos_finais) if tempos_finais else 0)
                fim = inicio + duracao

                if len(disponibilidade_estacao[estacao]) >= capacidade_estacao and not gargalo_ocorrido and inicio > 0:
                    gargalo_ocorrido = True
                    tempo_gargalo = inicio

                disponibilidade_estacao[estacao][idx_livre] = fim
                tempo_por_estacao[estacao] += duracao
                tempos_finais.append(fim)

            tempo_caixas[caixa] = max(tempos_finais) + tempo_adicional_caixa
            tempo_total_simulacao = max(tempo_total_simulacao, tempo_caixas[caixa])

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
            "df_simulacao": df
        }

        st.session_state.simulacoes_salvas[id_simulacao] = st.session_state.ultima_simulacao
        st.session_state.ordem_simulacoes.append(id_simulacao)

        if len(st.session_state.simulacoes_salvas) > 5:
            ids = sorted(st.session_state.simulacoes_salvas)[-5:]
            st.session_state.simulacoes_salvas = {k: st.session_state.simulacoes_salvas[k] for k in ids}
            st.session_state.ordem_simulacoes = ids




        # --- Exibição dos resultados no lado direito ---
        with col_dir:
            st.subheader("📊 Resultados da Simulação")
            st.write(f"🔚 **Tempo total para separar todas as caixas:** {formatar_tempo(tempo_total_simulacao)}")
            st.write(f"📦 **Total de caixas simuladas:** {len(caixas)}")
            st.write(f"🧱 **Tempo até o primeiro gargalo:** {formatar_tempo(tempo_gargalo) if gargalo_ocorrido else 'Nenhum gargalo'}")

            # Relatório detalhado por caixa
            df_relatorio_caixas = pd.DataFrame([
                {"Caixa": cx, "Tempo total da caixa (s)": t, "Tempo formatado": formatar_tempo(t)}
                for cx, t in tempo_caixas.items()
            ])
            df_relatorio_caixas = df_relatorio_caixas.sort_values(by="Tempo total da caixa (s)", ascending=False)
            st.markdown("### 🗂️ Relatório detalhado por Caixa")
            st.dataframe(df_relatorio_caixas)

            # Relatório por loja, se houver coluna ID_Loja
            if "ID_Loja" in df.columns:
                df_caixas_loja = df[["ID_Caixas", "ID_Loja"]].drop_duplicates()
                df_caixas_loja["Tempo_caixa"] = df_caixas_loja["ID_Caixas"].map(tempo_caixas)
                df_relatorio_loja = df_caixas_loja.groupby("ID_Loja").agg(
                    Total_Caixas=("ID_Caixas", "count"),
                    Tempo_Total_Segundos=("Tempo_caixa", "sum")
                ).reset_index()
                df_relatorio_loja["Tempo Formatado"] = df_relatorio_loja["Tempo_Total_Segundos"].apply(formatar_tempo)
                
                st.markdown("### 🏬 Relatório resumido por Loja")
                st.dataframe(df_relatorio_loja.sort_values(by="Tempo_Total_Segundos", ascending=False))

            # --- Geração do relatório Excel ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                # Planilha de Resumo
                df_resumo = pd.DataFrame({
                    "Descrição": [
                        f"Tempo médio por produto: {tempo_produto}s",
                        f"Tempo entre estações: {tempo_deslocamento}s",
                        f"Capacidade por estação: {capacidade_estacao}",
                        f"Pessoas por estação: {pessoas_por_estacao}",
                        f"Tempo adicional por caixa: {tempo_adicional_caixa}s",
                        "",
                        f"Tempo total da simulação: {formatar_tempo(tempo_total_simulacao)}",
                        f"Total de caixas: {len(caixas)}",
                        f"Tempo até o primeiro gargalo: {formatar_tempo(tempo_gargalo) if gargalo_ocorrido else 'Nenhum gargalo'}"
                    ]
                })
                df_resumo.to_excel(writer, sheet_name="Resumo_Simulação", index=False)

                # Planilha detalhada por caixa
                df_relatorio_caixas.to_excel(writer, sheet_name="Por_Caixa", index=False)

                # Planilha resumida por loja
                if "ID_Loja" in df.columns:
                    df_relatorio_loja.to_excel(writer, sheet_name="Por_Loja", index=False)

            relatorio_bytes = buffer.getvalue()

            st.download_button(
                label="📥 Baixar Relatórios",
                data=relatorio_bytes,
                file_name=f"Relatorio_Simulacao_{data_hora}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )


        # --- Sugestão de Layout Otimizado ---
        st.markdown("---")
        st.subheader("🧠 Sugestão de Layout Otimizado")

        df_estacoes = pd.DataFrame([
            {"Estação": est, "Tempo Total (s)": tempo} for est, tempo in tempo_por_estacao.items()
        ])
        
        tempo_medio = df_estacoes["Tempo Total (s)"].mean()
        limite_sobrecarga = tempo_medio * 1.5
        estacoes_sobrec = df_estacoes[df_estacoes["Tempo Total (s)"] > limite_sobrecarga]

        if not estacoes_sobrec.empty:
            st.warning("⚠️ Estações sobrecarregadas detectadas. Sugestão: redistribuir produtos das seguintes estações:")
            st.dataframe(estacoes_sobrec.assign(Sugestao="Redistribuir produtos para estações abaixo da média."))
        else:
            st.success("✅ Nenhuma estação sobrecarregada detectada.")

    except Exception as e:
        st.error(f"Erro durante a simulação: {e}")

# --- Comparação entre Simulações ou Arquivo Externo ---
st.markdown("---")
st.subheader("🔁 Comparação entre Simulações ou com Arquivo Externo")

uploaded_comp = st.file_uploader("📂 Arquivo para Comparação", type=["xlsx"], key="upload_comparacao")

ids_salvos = st.session_state.ordem_simulacoes[-2:]
tem_simulacoes = len(ids_salvos) >= 2
tem_arquivo_comp = uploaded_comp is not None

if tem_simulacoes or tem_arquivo_comp:
    if tem_arquivo_comp:
        try:
            df_comp_ext = pd.read_excel(uploaded_comp)
            df_comp_ext = df_comp_ext.sort_values(by=["ID_Pacote", "ID_Caixas"])
            tempo_por_estacao_ext = defaultdict(float)

            for _, linha in df_comp_ext.iterrows():
                estacao = linha["Estação"]
                contagem = linha["Contagem de Produto"]
                tempo = (contagem * tempo_produto) / pessoas_por_estacao + tempo_deslocamento
                tempo_por_estacao_ext[estacao] += tempo

            df_comp_ext_final = pd.DataFrame([
                {"Estação": est, "Tempo (s)": tempo, "Fonte": "Arquivo Comparado"}
                for est, tempo in tempo_por_estacao_ext.items()
            ])

            sim_atual = st.session_state.ultima_simulacao
            df_sim_atual = pd.DataFrame([
                {"Estação": est, "Tempo (s)": tempo, "Fonte": "Última Simulação"}
                for est, tempo in sim_atual["tempo_por_estacao"].items()
            ])

            df_comparativo = pd.concat([df_sim_atual, df_comp_ext_final])

            fig = px.bar(df_comparativo, x="Estação", y="Tempo (s)", color="Fonte", barmode="group",
                         title="⏳ Comparativo de Tempo por Estação")
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao processar o arquivo de comparação: {e}")

    elif tem_simulacoes:
        id1, id2 = ids_salvos[-2], ids_salvos[-1]
        sim1 = st.session_state.simulacoes_salvas[id1]
        sim2 = st.session_state.simulacoes_salvas[id2]

        df1 = pd.DataFrame([
            {"Estação": est, "Tempo (s)": tempo, "Fonte": f"Simulação {id1}"}
            for est, tempo in sim1["tempo_por_estacao"].items()
        ])
        df2 = pd.DataFrame([
            {"Estação": est, "Tempo (s)": tempo, "Fonte": f"Simulação {id2}"}
            for est, tempo in sim2["tempo_por_estacao"].items()
        ])

        df_comparativo = pd.concat([df1, df2])

        fig = px.bar(df_comparativo, x="Estação", y="Tempo (s)", color="Fonte", barmode="group",
                     title="⏳ Comparativo de Tempo por Estação")
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Realize ao menos duas simulações ou envie um arquivo para comparar.")

