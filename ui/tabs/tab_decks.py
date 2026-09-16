"""
ui/tabs/tab_decks.py - Aba 5: Gerenciador & Editor de Decks (FaBrary / Workspace).

Permite listar e excluir decks salvos, editar estrutura JSON e nome/formato,
e importar novos decks do FaBrary com validação estrita contra o banco de dados de cartas.
"""

import json
import streamlit as st
from deck_parser import (
    parse_deck_text,
    save_deck_to_workspace,
    set_active_deck,
    delete_saved_deck,
    update_saved_deck,
    validate_deck_against_db,
)
from ui.helpers import get_cached_saved_decks


def render_tab_decks(saved_decks=None, deck_options=None):
    """Renderiza a Aba 5: Gerenciador & Editor de Decks."""
    if saved_decks is None:
        saved_decks = get_cached_saved_decks()

    if deck_options is None:
        deck_options = {
            f"{d.get('name', d.get('slug'))} ({str(d.get('format', 'blitz')).upper()} - {d.get('total_cards', 0)} cartas)": d.get("slug")
            for d in saved_decks
        }

    st.subheader("📦 Gerenciador & Editor de Decks (FaBrary / Workspace)")
    tab_list, tab_edit_deck, tab_import = st.tabs(["📚 Decks Salvos & Exclusão", "✏️ Editor de Deck", "📥 Importar do FaBrary"])

    with tab_list:
        if saved_decks:
            st.markdown("### 📋 Decks Disponíveis no Workspace")
            for d in saved_decks:
                with st.container():
                    c_d1, c_d2, c_d3, c_d4 = st.columns([3, 2, 2, 2])
                    with c_d1:
                        st.markdown(f"**{d['name']}**")
                        st.caption(f"Slug: `{d['slug']}`")
                    with c_d2:
                        st.write(f"🏷️ **Formato:** {d['format'].upper()}")
                    with c_d3:
                        st.write(f"🃏 **Total:** {d['total_cards']} cartas")
                    with c_d4:
                        if st.button(f"🗑️ Deletar", key=f"del_{d['slug']}", type="secondary"):
                            delete_saved_deck(d["slug"])
                            get_cached_saved_decks.clear()
                            st.toast(f"Deck '{d['name']}' deletado!", icon="🗑️")
                            st.success(f"Deck **{d['name']}** deletado com sucesso!")
                            st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                    st.divider()
        else:
            st.info("Nenhum deck cadastrado ainda. Use a aba ao lado para importar seu primeiro deck.")

    with tab_edit_deck:
        if saved_decks:
            edit_choice = st.selectbox("Selecione o Deck para Editar:", list(deck_options.keys()), key="deck_editor_select")
            edit_slug = deck_options[edit_choice]
            deck_target = next((d for d in saved_decks if d["slug"] == edit_slug), None)
            if deck_target:
                d_curr = deck_target["data"]
                c_ed1, c_ed2 = st.columns([2, 1])
                with c_ed1:
                    new_name_val = st.text_input("Nome do Deck:", value=d_curr.get("name", ""), key=f"ed_name_{edit_slug}")
                with c_ed2:
                    new_fmt_val = st.selectbox("Formato:", ["cc", "blitz"], index=0 if d_curr.get("format") == "cc" else 1, key=f"ed_fmt_{edit_slug}")

                st.markdown("#### 🃏 Lista de Cartas do Deck (JSON / Quantidades):")
                cards_raw_str = json.dumps(d_curr.get("cards", []), indent=2)
                edited_cards_text = st.text_area("Estrutura das Cartas:", value=cards_raw_str, height=260, key=f"ed_cards_{edit_slug}")

                c_save_b1, c_save_b2 = st.columns([1, 1])
                with c_save_b1:
                    if st.button("💾 Salvar Alterações no Deck", type="primary", use_container_width=True):
                        try:
                            parsed_cards = json.loads(edited_cards_text)
                            update_saved_deck(edit_slug, new_name_val, new_fmt_val, parsed_cards)
                            get_cached_saved_decks.clear()
                            st.toast(f"Deck '{new_name_val}' atualizado com sucesso!", icon="💾")
                            st.success(f"Alterações salvas no deck **{new_name_val}**!")
                            st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar alterações no JSON das cartas: {e}")
                with c_save_b2:
                    if st.button("🌟 Definir como Deck Ativo Padrão", use_container_width=True):
                        set_active_deck(d_curr)
                        st.toast(f"Deck '{d_curr.get('name')}' definido como padrão!", icon="🌟")
        else:
            st.info("Nenhum deck para editar.")

    with tab_import:
        st.markdown("Cole abaixo o texto exportado diretamente do **FaBrary** (ou FabDB):")
        col_imp1, col_imp2 = st.columns([3, 2])

        # Controle de versão do formulário para garantir limpeza confiável dos campos após importação
        if "import_form_id" not in st.session_state:
            st.session_state["import_form_id"] = 0
        if "import_errors" not in st.session_state:
            st.session_state["import_errors"] = []

        form_id = st.session_state["import_form_id"]

        with col_imp1:
            deck_text_input = st.text_area(
                "Texto do Deck (FaBrary / FabDB):",
                height=230,
                key=f"deck_import_text_{form_id}",
                placeholder="""Name: Calling: Hamburg 1st 🇩🇪\nHero: Dash I/O\nFormat: Classic Constructed\n\nArena cards\n1x Achilles Accelerator\n1x Symbiosis Shot\n\nDeck cards\n3x Backup Protocol: RED (red)\n3x Zero to Sixty (red)""",
            )
            col_b1, col_b2, col_b3 = st.columns([3, 2, 1])
            with col_b1:
                custom_name = st.text_input(
                    "Nome Customizado do Deck (opcional):",
                    key=f"deck_import_name_{form_id}",
                    placeholder="Ex: Dash CC Pro",
                )
            with col_b2:
                st.write("")
                st.write("")
                btn_save = st.button("💾 Importar e Validar Deck", type="primary", use_container_width=True)
            with col_b3:
                st.write("")
                st.write("")
                if st.button("🧹 Limpar", use_container_width=True, help="Limpa o texto e erros do formulário"):
                    st.session_state["import_form_id"] = form_id + 1
                    st.session_state["import_errors"] = []
                    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

            if btn_save:
                if deck_text_input and deck_text_input.strip():
                    parsed = parse_deck_text(deck_text_input, default_name=custom_name if custom_name else "Meu Deck")
                    if custom_name and custom_name.strip():
                        parsed["name"] = custom_name.strip()

                    is_valid, errors, meta_info = validate_deck_against_db(parsed)
                    if not is_valid:
                        st.session_state["import_errors"] = errors
                        st.toast("⚠️ Inconsistências encontradas no Deck!", icon="⚠️")
                    else:
                        res = save_deck_to_workspace(parsed)
                        get_cached_saved_decks.clear()
                        st.session_state["import_form_id"] = form_id + 1
                        st.session_state["import_errors"] = []
                        st.session_state["last_imported_deck"] = parsed
                        st.toast(f"✅ Deck '{parsed['name']}' ({parsed['format'].upper()}) importado com sucesso!", icon="🎉")
                        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                else:
                    st.warning("Cole o texto do deck antes de clicar em salvar.")

            if "last_imported_deck" in st.session_state:
                p = st.session_state.pop("last_imported_deck")
                st.success(f"🎉 **Deck Validado e Importado com Sucesso!**\n- **Nome:** {p['name']}\n- **Formato:** {p['format'].upper()}\n- **Total de Cartas:** {sum(c.get('total', 1) for c in p['cards'])}")

        with col_imp2:
            if st.session_state.get("import_errors"):
                st.error("### ⚠️ Erros de Validação do Deck\n" + "\n".join(f"• **{e}**" for e in st.session_state["import_errors"]))
                st.info("💡 Corrija as inconsistências na caixa de texto ao lado e clique novamente em 'Importar e Validar Deck'.")
            else:
                st.info("""💡 **Validador Estrito do Talishar:**\n- Validação automática de 10.000+ cartas suportadas no motor\n- Reconhecimento de Hero e slots de equipamentos (Head, Chest, Arms, Legs, Weapons)\n- Trava de importação se houver cartas não suportadas\n- Preservação do texto para correção imediata""")
