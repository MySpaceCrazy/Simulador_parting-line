# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import plotly.express as px
from datetime import datetime
from pathlib import Path
import pytz

#st.set_page_config(page_title="Simulador de Separação de Produtos", layout="wide")
st.set_page_config(
    page_title="Simulador de Separação de Produtos",
    page_icon="https://raw.githubusercontent.com/MySpaceCrazy/Simulador_parting-line/refs/heads/main/pacotes.ico",
    layout="wide"
)

# --- Função de formatação ---
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

# --- Cabeçalho ---
col_titulo, col_botao, col_download, col_vazio = st.columns([5, 2, 2, 1])

with col_titulo:
    st.title("🧪 Simulador de Separação de Produtos")

with col_botao:
    iniciar = st.button("▶️ Iniciar Simulação", use_container_width=True)

with col_download:
    if "ultima_simulacao" in st.session_state and st.session_state.ultima_simulacao:
        sim = st.session_state.ultima_simulacao
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            parametros = {
                "Tempo médio por produto (s)": st.session_state.get("tempo_produto", ""),
                "Tempo entre estações (s)": st.session_state.get("tempo_deslocamento", ""),
                "Capacidade por estação": st.session_state.get("capacidade_estacao", ""),
                "Pessoas por estação": st.session_state.get("pessoas_por_estacao", ""),
                "Tempo adicional por caixa (s)": st.session_state.get("tempo_adicional_caixa", ""),
                "Total de caixas simuladas": sim["total_caixas"],
                "Tempo total simulação": formatar_tempo(sim["tempo_total"]),
                "Tempo até o primeiro gargalo": formatar_tempo(sim["gargalo"]) if sim.get("gargalo") else "Nenhum gargalo"
            }
            df_resumo = pd.DataFrame(list(parametros.items()), columns=["Descrição", "Valor"])
            df_resumo.to_excel(writer, sheet_name="Resumo_Simulação", index=False)

            df_caixas = pd.DataFrame([
                {"Caixa": cx, "Tempo total (s)": t, "Tempo formatado": formatar_tempo(t)}
                for cx, t in sim["tempo_caixas"].items()
            ])
            df_caixas.sort_values(by="Tempo total (s)", ascending=False).to_excel(writer, sheet_name="Por_Caixa", index=False)

            df_sim = sim.get("df_simulacao")
            if df_sim is not None and "ID_Loja" in df_sim.columns:
                df_temp = df_sim[["ID_Caixas", "ID_Loja"]].drop_duplicates()
                df_temp["Tempo_caixa"] = df_temp["ID_Caixas"].map(sim["tempo_caixas"])
                df_loja = df_temp.groupby("ID_Loja").agg(
                    Total_Caixas=("ID_Caixas", "count"),
                    Tempo_Total_Segundos=("Tempo_caixa", "max")
                ).reset_index()

                df_loja["Tempo formatado"] = df_loja["Tempo_Total_Segundos"].apply(formatar_tempo)
                df_loja.to_excel(writer, sheet_name="Por_Loja", index=False)

            if "df_comp" in st.session_state and not st.session_state.df_comp.empty:
                st.session_state.df_comp.to_excel(writer, sheet_name="Comparativo", index=False)

        st.download_button(
            label="📥 Baixar Relatórios",
            data=buffer.getvalue(),
            file_name="Relatorio_Simulacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# --- Parâmetros de Simulação ---
col_esq, col_dir = st.columns([2, 2])

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

# Salva o arquivo no estado, se for novo upload
if novo_arquivo is not None:
    st.session_state.arquivo_atual = novo_arquivo

# Usa o arquivo do estado, se disponível
uploaded_file = st.session_state.get("arquivo_atual", None)

# Inicializa session_state
if "simulacoes_salvas" not in st.session_state:
    st.session_state.simulacoes_salvas = {}
if "ultima_simulacao" not in st.session_state:
    st.session_state.ultima_simulacao = {}
if "ordem_simulacoes" not in st.session_state:
    st.session_state.ordem_simulacoes = []

# Upload Comparação externo

with col_esq:
    ver_graficos = st.checkbox("📊 Ver gráficos e dashboards", value=True, disabled=True, key="ver_graficos")
    comparar_simulacoes = st.checkbox("🔁 Comparar com simulações anteriores ou Excel", value=True, disabled=True, key="comparar_simulacoes")
        
# --- Início da Simulação ---
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

            fim_caixa_absoluto = max(tempos_finais) + tempo_adicional_caixa if tempos_finais else 0
            tempo_caixas[caixa] = fim_caixa_absoluto  # Guardar o tempo absoluto final da caixa
            tempo_total_simulacao = max(tempo_total_simulacao, fim_caixa_absoluto)


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
            "df_simulacao": df
        }

        # ⚠️ Validação correta: Caixa associada a mais de uma loja
        df_lojas_por_caixa = df.groupby("ID_Caixas")["ID_Loja"].nunique().reset_index()
        df_caixas_multiplas_lojas = df_lojas_por_caixa[df_lojas_por_caixa["ID_Loja"] > 1]
        
        if not df_caixas_multiplas_lojas.empty:
            st.warning("⚠️ Atenção: Existem caixas associadas a mais de uma loja, verifique o arquivo!")
            caixas_com_problema = df_caixas_multiplas_lojas["ID_Caixas"].tolist()
            df_problema = df[df["ID_Caixas"].isin(caixas_com_problema)].sort_values(by=["ID_Caixas", "ID_Loja", "Estação"])
            st.dataframe(df_problema)

            
        st.session_state.simulacoes_salvas[id_simulacao] = st.session_state.ultima_simulacao
        st.session_state.ordem_simulacoes.append(id_simulacao)

        if len(st.session_state.simulacoes_salvas) > 5:
            ids = sorted(st.session_state.simulacoes_salvas)[-5:]
            st.session_state.simulacoes_salvas = {k: st.session_state.simulacoes_salvas[k] for k in ids}
            st.session_state.ordem_simulacoes = ids

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        
# --- Exibição do último resultado e relatórios ---
col_esq, col_dir = st.columns([2, 2])

st.markdown("---")

if "ultima_simulacao" in st.session_state and st.session_state.ultima_simulacao:
    tempo_total = st.session_state.ultima_simulacao.get("tempo_total", None)
    gargalo = st.session_state.ultima_simulacao.get("gargalo", None)
    caixas = st.session_state.ultima_simulacao.get("total_caixas", 0)

    if tempo_total is not None:
        st.subheader("📊 Resultados da Simulação")
        st.write(f"🔚 **Tempo total para separar todas as caixas:** {formatar_tempo(tempo_total)}")
        st.write(f"📦 **Total de caixas simuladas:** {caixas}")
        st.write(f"🧱 **Tempo até o primeiro gargalo:** {formatar_tempo(gargalo) if gargalo else 'Nenhum gargalo'}")
        
else:
    st.info("Nenhuma simulação realizada ainda.")
        
with col_esq:
    if "ultima_simulacao" in st.session_state and st.session_state.ultima_simulacao:
        sim = st.session_state.ultima_simulacao
        tempo_total = sim.get("tempo_total", None)
        gargalo = sim.get("gargalo", None)
        tempo_por_estacao = sim.get("tempo_por_estacao", {})
        caixas = sim.get("total_caixas", 0)
        tempo_caixas = sim.get("tempo_caixas", {})
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
            df_caixas_loja = df_sim.groupby("ID_Caixas").agg(ID_Loja=("ID_Loja", "first")).reset_index()
            df_caixas_loja["Tempo_caixa"] = df_caixas_loja["ID_Caixas"].map(tempo_caixas)
            df_relatorio_loja = df_caixas_loja.groupby("ID_Loja").agg(
                Total_Caixas=("ID_Caixas", "count"),
                Tempo_Total_Segundos=("Tempo_caixa", "max")
            ).reset_index()

            with col_dir:
                df_relatorio_loja["Tempo Formatado"] = df_relatorio_loja["Tempo_Total_Segundos"].apply(formatar_tempo)
                st.markdown("### 🏬 Relatório resumido por Loja")
                st.dataframe(df_relatorio_loja.sort_values(by="Tempo_Total_Segundos", ascending=False))

# --- Comparação com simulações anteriores ou arquivo externo ---
st.markdown("---")

if comparar_simulacoes:
    ids = st.session_state.ordem_simulacoes[-2:]  # últimas 2 simulações

    if len(ids) < 2 and not st.session_state.get("df_comp", pd.DataFrame()).empty:
        st.info("Nenhuma comparação possível: faça pelo menos duas simulações ou envie um arquivo para comparação.")
    else:
        df_comp = pd.DataFrame()
        tempo1 = caixas1 = tempo2 = caixas2 = 0
        sim1 = None
        sim2_label = ""

        # Se existir arquivo para comparação externo
        uploaded_comp = st.session_state.get("arquivo_comparacao", None)
        if uploaded_comp:
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
                        tempo = (contagem * st.session_state.tempo_produto) / st.session_state.pessoas_por_estacao + st.session_state.tempo_deslocamento
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
        else:
            # Comparação entre últimas 2 simulações salvas
            if len(ids) == 2:
                id1, id2 = ids[-2], ids[-1]
                sim1 = st.session_state.simulacoes_salvas.get(id1)
                sim2 = st.session_state.simulacoes_salvas.get(id2)
                if sim1 and sim2:
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
                    df_comp = pd.concat([df1, df2], ignore_index=True)

        # Mostrar gráfico e métricas se tiver dados
        if not df_comp.empty and sim1 is not None:
            st.markdown("### 📊 Comparativo de Tempo por Estação")
            fig_comp = px.bar(df_comp, x="Estação", y="Tempo (s)", color="Simulação", barmode="group")
            st.plotly_chart(fig_comp, use_container_width=True)

            delta_tempo = tempo2 - tempo1
            abs_pct = abs(delta_tempo / tempo1 * 100) if tempo1 else 0
            direcao = "melhorou" if delta_tempo < 0 else "aumentou"

            caixas_diferenca = caixas2 - caixas1
            caixas_pct = (caixas_diferenca / caixas1 * 100) if caixas1 else 0

            tempo_formatado = formatar_tempo(abs(delta_tempo))
            # delta_color='inverse' para verde se diminuiu tempo
            st.metric(
                "Delta de Tempo Total",
                f"{tempo_formatado}",
                f"{delta_tempo:+.0f}s ({abs_pct:.1f}% {direcao})",
                delta_color="inverse"
            )

            st.write(f"📦 **Caixas Base:** {caixas1} | **Comparada:** {caixas2} | Δ {caixas_diferenca:+} caixas ({caixas_pct:+.1f}%)")

st.markdown("---")

# --- Seção Autor ---
col6 = st.columns(1)
st.markdown("""
<style>
.author {
    padding: 40px 20px;
    text-align: center;
    background-color: #000000;
    color: white;
}

.author img {
    width: 120px;
    height: 120px;
    border-radius: 50%;
}

.author p {
    margin-top: 15px;
    font-size: 1rem;
}
</style>

<style>
    .author-name {
        font-weight: bold;
        font-size: 1.4rem;
        color: white;
    }
</style>

<div class="author">
    <img src="https://avatars.githubusercontent.com/u/90271653?v=4" alt="Autor">
    <div class="author-name">
        <p>Ânderson Oliveira</p>
    </div>    
    <p>Engenheiro de Dados</p>
    <p>Análise e Desenvolvimento de Sistemas</p>
    <p>Desenvolvedor de soluções em logística e automações</p>
    <div style="margin: 10px 0;">
        <a href="https://github.com/MySpaceCrazy" target="_blank">
            <img src="https://raw.githubusercontent.com/MySpaceCrazy/Simulador_parting-line/refs/heads/main/github.ico" alt="GitHub" style="width: 32px; height: 32px; margin-right: 10px;">
        </a>
        <a href="https://www.linkedin.com/in/%C3%A2nderson-matheus-flores-de-oliveira-5b92781b4" target="_blank">
            <img src="https://raw.githubusercontent.com/MySpaceCrazy/Simulador_parting-line/refs/heads/main/linkedin.ico" alt="LinkedIn" style="width: 32px; height: 32px;">
        </a>
    </div>
</div>
""", unsafe_allow_html=True)
