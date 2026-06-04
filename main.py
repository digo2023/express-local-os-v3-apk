# -*- coding: utf-8 -*-
"""
GESTÃO DE ESTOQUE EXPRESS COLORADO — APK PREMIUM ESTÁVEL
Versão revisada para Android/Samsung A06.

Correção principal: a tela anterior usava um terminal interno + Thread + stdin/stdout.
Em alguns aparelhos Android/Kivy o toque abria execução bloqueante ou não respondia,
causando sensação de aplicativo travado. Esta versão usa botões nativos reais,
popups próprios, SQLite direto e ações rápidas sem bloquear a interface.
"""
from __future__ import annotations

import csv
import os
import sqlite3
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle, Rectangle, Ellipse
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.floatlayout import FloatLayout

try:
    from kivy.utils import platform
except Exception:  # pragma: no cover
    platform = "unknown"

APP_TITLE = "Gestão de Estoque Express Colorado"
DB_NAME = "express_operacional.db"

NAVY = (0.004, 0.010, 0.026, 1)
CARD = (0.010, 0.027, 0.060, 0.98)
CARD_2 = (0.014, 0.038, 0.082, 0.98)
BLUE = (0.000, 0.565, 1.000, 1)
GOLD = (1.000, 0.590, 0.020, 1)
GREEN = (0.040, 0.820, 0.410, 1)
RED = (1.000, 0.250, 0.220, 1)
WHITE = (0.940, 0.960, 0.985, 1)
MUTED = (0.670, 0.720, 0.800, 1)
BORDER_BLUE = (0.000, 0.480, 1.000, 0.70)
BORDER_GOLD = (1.000, 0.545, 0.000, 0.72)
BORDER_DIM = (0.100, 0.285, 0.570, 0.42)

CATEGORIAS = ["CONGELADO", "RESFRIADO", "NÃO PERECÍVEL", "HORTIFRUTI", "LIMPEZA", "DESCARTÁVEL", "PROTEÍNAS", "OUTROS"]
UNIDADES = ["KG", "G", "UN", "PACOTE", "CX", "FARDO", "L", "ML"]
TURNOS = {"A": "ALMOÇO", "B": "JANTA", "C": "CEIA"}


def agora_br() -> datetime:
    return datetime.now(timezone(timedelta(hours=-3), name="BRT"))


def data_br() -> str:
    return agora_br().strftime("%d/%m/%Y")


def hora_br() -> str:
    return agora_br().strftime("%H:%M")


def stamp() -> str:
    return agora_br().strftime("%Y%m%d_%H%M%S")


def normalizar_numero(txt: str) -> float:
    txt = (txt or "").strip().replace(".", "").replace(",", ".")
    if not txt:
        return 0.0
    return float(txt)


def moeda(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def qtd_fmt(v: float) -> str:
    if abs(v - int(v)) < 0.0001:
        return str(int(v))
    return f"{v:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def app_dir() -> Path:
    if platform == "android":
        try:
            from android.storage import app_storage_path  # type: ignore
            p = Path(app_storage_path())
        except Exception:
            p = Path(os.environ.get("ANDROID_PRIVATE", "."))
        return p
    return Path(__file__).resolve().parent


BASE_DIR = app_dir()
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "relatorios"
BACKUP_DIR = BASE_DIR / "backups"
for pasta in (DATA_DIR, REPORT_DIR, BACKUP_DIR):
    pasta.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / DB_NAME


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.init()

    def conn(self):
        c = sqlite3.connect(str(self.path), timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=8000")
        return c

    def init(self):
        with self.conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS produtos(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT UNIQUE NOT NULL,
                    nome TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    unidade TEXT NOT NULL,
                    estoque_minimo REAL NOT NULL DEFAULT 0,
                    custo_unitario REAL NOT NULL DEFAULT 0,
                    localizacao TEXT DEFAULT 'GERAL',
                    observacao TEXT DEFAULT '',
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS estoque(
                    produto_id INTEGER PRIMARY KEY,
                    quantidade REAL NOT NULL DEFAULT 0,
                    atualizado_em TEXT NOT NULL,
                    FOREIGN KEY(produto_id) REFERENCES produtos(id)
                );
                CREATE TABLE IF NOT EXISTS movimentacoes(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produto_id INTEGER NOT NULL,
                    tipo TEXT NOT NULL,
                    quantidade REAL NOT NULL,
                    unidade TEXT NOT NULL,
                    data_movimento TEXT NOT NULL,
                    data_consumo TEXT DEFAULT '',
                    turno TEXT DEFAULT '',
                    observacao TEXT DEFAULT '',
                    estoque_antes REAL NOT NULL DEFAULT 0,
                    estoque_depois REAL NOT NULL DEFAULT 0,
                    criado_em TEXT NOT NULL,
                    FOREIGN KEY(produto_id) REFERENCES produtos(id)
                );
                CREATE TABLE IF NOT EXISTS notificacoes(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo TEXT NOT NULL,
                    mensagem TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDENTE',
                    criado_em TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome);
                CREATE INDEX IF NOT EXISTS idx_mov_data ON movimentacoes(data_movimento);
                """
            )

    def execute(self, sql: str, args: tuple = ()):
        with self.conn() as c:
            cur = c.execute(sql, args)
            c.commit()
            return cur.lastrowid

    def rows(self, sql: str, args: tuple = ()) -> List[sqlite3.Row]:
        with self.conn() as c:
            return c.execute(sql, args).fetchall()

    def row(self, sql: str, args: tuple = ()):  # -> sqlite3.Row | None
        with self.conn() as c:
            return c.execute(sql, args).fetchone()

    def cadastrar_produto(self, dados: Dict[str, str]):
        agora = agora_br().isoformat(timespec="seconds")
        codigo = dados["codigo"].strip().upper()
        nome = dados["nome"].strip().upper()
        categoria = dados.get("categoria", "OUTROS").strip().upper() or "OUTROS"
        unidade = dados.get("unidade", "UN").strip().upper() or "UN"
        minimo = normalizar_numero(dados.get("estoque_minimo", "0"))
        custo = normalizar_numero(dados.get("custo_unitario", "0"))
        local = dados.get("localizacao", "GERAL").strip().upper() or "GERAL"
        obs = dados.get("observacao", "").strip()
        pid = self.execute(
            """INSERT INTO produtos(codigo,nome,categoria,unidade,estoque_minimo,custo_unitario,localizacao,observacao,criado_em,atualizado_em)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (codigo, nome, categoria, unidade, minimo, custo, local, obs, agora, agora),
        )
        self.execute("INSERT OR REPLACE INTO estoque(produto_id,quantidade,atualizado_em) VALUES(?,?,?)", (pid, 0, agora))
        return pid

    def produtos(self) -> List[sqlite3.Row]:
        return self.rows(
            """SELECT p.*, COALESCE(e.quantidade,0) quantidade
               FROM produtos p LEFT JOIN estoque e ON e.produto_id=p.id
               WHERE p.ativo=1 ORDER BY p.nome"""
        )

    def produto_por_codigo_ou_nome(self, termo: str):
        termo = (termo or "").strip().upper()
        return self.row(
            """SELECT p.*, COALESCE(e.quantidade,0) quantidade FROM produtos p
               LEFT JOIN estoque e ON e.produto_id=p.id
               WHERE p.ativo=1 AND (p.codigo=? OR p.nome LIKE ?) ORDER BY p.nome LIMIT 1""",
            (termo, f"%{termo}%"),
        )

    def movimentar(self, produto_id: int, tipo: str, quantidade: float, data_consumo: str = "", turno: str = "", observacao: str = ""):
        produto = self.row("SELECT * FROM produtos WHERE id=? AND ativo=1", (produto_id,))
        if not produto:
            raise ValueError("Produto não encontrado.")
        est = self.row("SELECT quantidade FROM estoque WHERE produto_id=?", (produto_id,))
        antes = float(est["quantidade"] if est else 0)
        delta = quantidade if tipo == "ENTRADA" else -quantidade
        depois = antes + delta
        if depois < -0.0001:
            raise ValueError(f"Estoque insuficiente. Disponível: {qtd_fmt(antes)} {produto['unidade']}.")
        agora = agora_br().isoformat(timespec="seconds")
        self.execute("INSERT OR REPLACE INTO estoque(produto_id,quantidade,atualizado_em) VALUES(?,?,?)", (produto_id, depois, agora))
        self.execute(
            """INSERT INTO movimentacoes(produto_id,tipo,quantidade,unidade,data_movimento,data_consumo,turno,observacao,estoque_antes,estoque_depois,criado_em)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (produto_id, tipo, quantidade, produto["unidade"], data_br(), data_consumo, turno, observacao, antes, depois, agora),
        )
        if depois <= float(producto_min := produto["estoque_minimo"] or 0) and producto_min > 0:
            self.execute(
                "INSERT INTO notificacoes(tipo,mensagem,status,criado_em) VALUES(?,?,?,?)",
                ("ESTOQUE_BAIXO", f"{produto['nome']} abaixo do mínimo: {qtd_fmt(depois)} {produto['unidade']}", "PENDENTE", agora),
            )
        return antes, depois

    def indicadores(self) -> Dict[str, float]:
        p = self.row("SELECT COUNT(*) c FROM produtos WHERE ativo=1")["c"]
        baixo = self.row(
            """SELECT COUNT(*) c FROM produtos p LEFT JOIN estoque e ON e.produto_id=p.id
               WHERE p.ativo=1 AND p.estoque_minimo>0 AND COALESCE(e.quantidade,0)<=p.estoque_minimo"""
        )["c"]
        mov_dia = self.row("SELECT COUNT(*) c FROM movimentacoes WHERE data_movimento=?", (data_br(),))["c"]
        consumo = self.row(
            """SELECT COALESCE(SUM(m.quantidade*p.custo_unitario),0) total
               FROM movimentacoes m JOIN produtos p ON p.id=m.produto_id
               WHERE m.tipo='SAIDA' AND m.data_movimento=?""",
            (data_br(),),
        )["total"]
        pend = self.row("SELECT COUNT(*) c FROM notificacoes WHERE status='PENDENTE'")["c"]
        return {"produtos": p, "baixo": baixo, "mov_dia": mov_dia, "consumo": consumo, "pendentes": pend}

    def estoque_baixo(self) -> List[sqlite3.Row]:
        return self.rows(
            """SELECT p.codigo,p.nome,p.unidade,p.estoque_minimo,COALESCE(e.quantidade,0) quantidade,p.localizacao
               FROM produtos p LEFT JOIN estoque e ON e.produto_id=p.id
               WHERE p.ativo=1 AND p.estoque_minimo>0 AND COALESCE(e.quantidade,0)<=p.estoque_minimo
               ORDER BY p.nome"""
        )

    def ultimas_mov(self, limite=80) -> List[sqlite3.Row]:
        return self.rows(
            """SELECT m.*,p.codigo,p.nome FROM movimentacoes m JOIN produtos p ON p.id=m.produto_id
               ORDER BY m.id DESC LIMIT ?""",
            (limite,),
        )


DB = Database(DB_PATH)


class Fundo(FloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*NAVY)
            self.bg = Rectangle(pos=self.pos, size=self.size)
            Color(0.0, 0.25, 0.60, 0.17)
            self.halo1 = Ellipse()
            Color(1.0, 0.48, 0.0, 0.10)
            self.halo2 = Ellipse()
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.bg.pos = self.pos
        self.bg.size = self.size
        self.halo1.pos = (self.width - dp(220), self.height - dp(190))
        self.halo1.size = (dp(290), dp(290))
        self.halo2.pos = (-dp(130), -dp(90))
        self.halo2.size = (dp(260), dp(260))


class Card(BoxLayout):
    def __init__(self, borda=BORDER_BLUE, cor=CARD, raio=20, **kw):
        super().__init__(**kw)
        self.borda = borda
        self.cor = cor
        self.raio = raio
        with self.canvas.before:
            Color(*self.cor)
            self.r = RoundedRectangle(radius=[dp(self.raio)])
            Color(*self.borda)
            self.l = Line(width=dp(1.15), rounded_rectangle=(0, 0, 1, 1, dp(self.raio)))
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.r.pos = self.pos
        self.r.size = self.size
        self.l.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(self.raio))


class Botao(Button):
    def __init__(self, borda=BORDER_BLUE, cor=CARD_2, raio=20, **kw):
        super().__init__(**kw)
        self.markup = True
        self.bold = True
        self.halign = "center"
        self.valign = "middle"
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = WHITE
        self.borda = borda
        self.cor = cor
        self.raio = raio
        with self.canvas.before:
            Color(*self.cor)
            self.r = RoundedRectangle(radius=[dp(self.raio)])
            Color(*self.borda)
            self.l = Line(width=dp(1.25), rounded_rectangle=(0, 0, 1, 1, dp(self.raio)))
        self.bind(pos=self._redraw, size=self._redraw)
        self.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0] - dp(8), val[1] - dp(4))))

    def _redraw(self, *_):
        self.r.pos = self.pos
        self.r.size = self.size
        self.l.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(self.raio))


class Texto(Label):
    def __init__(self, text="", fs="13sp", color=WHITE, bold=False, halign="left", **kw):
        super().__init__(text=text, font_size=fs, color=color, bold=bold, markup=True, halign=halign, valign="middle", **kw)
        self.bind(size=lambda inst, val: setattr(inst, "text_size", val))


class Campo(TextInput):
    def __init__(self, hint="", **kw):
        super().__init__(hint_text=hint, multiline=False, font_size="15sp", foreground_color=WHITE,
                         hint_text_color=(0.62, 0.66, 0.72, 1), background_normal="", background_active="",
                         background_color=(0.012, 0.027, 0.055, 0.98), cursor_color=GOLD,
                         padding=(dp(10), dp(12), dp(10), dp(10)), **kw)


class SistemaTela(Fundo):
    def __init__(self, **kw):
        super().__init__(**kw)
        Window.clearcolor = NAVY
        self.area = None
        self.toast_popup = None
        self._montar()
        Clock.schedule_once(lambda *_: self.mostrar_painel(), 0.1)
        self._pedir_permissoes()

    def _pedir_permissoes(self):
        if platform != "android":
            return
        try:
            from android.permissions import request_permissions, Permission  # type: ignore
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
        except Exception:
            pass

    def _montar(self):
        root = BoxLayout(orientation="vertical", spacing=dp(7), padding=(dp(9), dp(6), dp(9), dp(7)))
        self.add_widget(root)

        header = Card(orientation="horizontal", size_hint_y=None, height=dp(96), padding=dp(8), spacing=dp(9), borda=BORDER_DIM)
        logo = self._logo()
        header.add_widget(logo)
        texts = BoxLayout(orientation="vertical")
        texts.add_widget(Texto("[color=1AA9FF][b]GESTÃO DE ESTOQUE[/b][/color]", "13sp", BLUE, True))
        texts.add_widget(Texto("[b]EXPRESS COLORADO[/b]", "20sp", WHITE, True))
        texts.add_widget(Texto("[color=FF9A12][b]Operação, compras e conferência[/b][/color]", "11sp", GOLD, True))
        header.add_widget(texts)
        b_alertas = Botao(text="[b]ALERTAS[/b]", font_size="10sp", size_hint=(None, 1), width=dp(78), borda=BORDER_GOLD)
        b_alertas.bind(on_release=lambda *_: self.mostrar_alertas())
        header.add_widget(b_alertas)
        root.add_widget(header)

        self.area = BoxLayout(orientation="vertical", size_hint=(1, 1))
        root.add_widget(self.area)

        nav = Card(orientation="horizontal", size_hint_y=None, height=dp(62), padding=dp(4), spacing=dp(4), borda=BORDER_BLUE)
        for nome, acao, ativo in [
            ("Início", self.mostrar_painel, False),
            ("Estoque", self.mostrar_estoque, False),
            ("Ações", self.mostrar_acoes, True),
            ("Relatórios", self.mostrar_relatorios, False),
            ("Mais", self.mostrar_mais, False),
        ]:
            btn = Botao(text=f"[b]{nome}[/b]", font_size="11sp", borda=BORDER_GOLD if ativo else (0, 0, 0, 0), raio=16)
            btn.bind(on_release=lambda _i, a=acao: self._safe(a))
            nav.add_widget(btn)
        root.add_widget(nav)

    def _logo(self):
        card = Card(size_hint=(None, 1), width=dp(88), padding=dp(4), borda=BORDER_BLUE)
        candidates = [Path(__file__).resolve().parent / "icon.png", Path(__file__).resolve().parent / "sistema_express" / "recursos" / "app_icon.png"]
        src = next((str(p) for p in candidates if p.exists()), "")
        if src:
            card.add_widget(Image(source=src, allow_stretch=True, keep_ratio=True))
        else:
            card.add_widget(Texto("[b]EXPRESS[/b]", "13sp", BLUE, True, "center"))
        return card

    def _safe(self, func, *args):
        try:
            return func(*args)
        except Exception as e:
            traceback.print_exc()
            self.msg(f"Falha controlada: {e}", erro=True)

    def _clear(self):
        self.area.clear_widgets()

    def _scroll(self):
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(5), scroll_type=["content", "bars"])
        content = BoxLayout(orientation="vertical", spacing=dp(9), padding=(0, 0, 0, dp(6)), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        self.area.add_widget(scroll)
        return content

    def msg(self, texto: str, erro=False):
        Popup(title="Aviso", content=Texto(texto, "14sp", RED if erro else WHITE, True, "center"),
              size_hint=(0.90, None), height=dp(180), separator_color=GOLD if not erro else RED).open()

    def _card_titulo(self, titulo: str, subtitulo: str = ""):
        c = Card(orientation="vertical", size_hint_y=None, height=dp(88), padding=dp(12), borda=BORDER_DIM)
        c.add_widget(Texto(f"[b]{titulo}[/b]", "22sp", WHITE, True))
        if subtitulo:
            c.add_widget(Texto(subtitulo, "12sp", MUTED))
        return c

    def mostrar_painel(self):
        self._clear()
        cont = self._scroll()
        ind = DB.indicadores()
        title = self._card_titulo("Painel Operacional", "Sistema premium estável, com botões reais e banco de dados local.")
        cont.add_widget(title)

        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(268))
        dados = [
            ("EST", "Itens cadastrados", str(ind["produtos"]), "produtos ativos", BLUE, BORDER_BLUE, self.mostrar_estoque),
            ("ALT", "Estoque baixo", str(ind["baixo"]), "reposição necessária", GOLD, BORDER_GOLD, self.mostrar_alertas),
            ("MOV", "Mov. hoje", str(ind["mov_dia"]), "entradas e saídas", BLUE, BORDER_BLUE, self.mostrar_historico),
            ("R$", "Consumo do dia", moeda(float(ind["consumo"])), f"atualizado {hora_br()}", GOLD, BORDER_GOLD, self.mostrar_relatorios),
        ]
        for simb, titulo, valor, rod, cor, borda, acao in dados:
            grid.add_widget(self._kpi(simb, titulo, valor, rod, cor, borda, acao))
        cont.add_widget(grid)

        quick = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(122))
        quick.add_widget(self._tile("ENT", "Nova entrada", "Registrar produto recebido", BLUE, BORDER_BLUE, self.form_entrada))
        quick.add_widget(self._tile("SAI", "Nova saída", "Baixar consumo por turno", GOLD, BORDER_GOLD, self.form_saida))
        cont.add_widget(quick)

        cont.add_widget(Texto("[b]Funções principais[/b]", "17sp", WHITE, True, size_hint_y=None, height=dp(34)))
        grid2 = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(498))
        for simb, titulo, sub, cor, borda, acao in [
            ("EST", "Estoque", "Produtos, saldos e localização", BLUE, BORDER_BLUE, self.mostrar_estoque),
            ("CONF", "Conferência", "Ajuste seguro do estoque", BLUE, BORDER_BLUE, self.form_conferencia),
            ("PLAN", "Planejamento", "Consumo e faltantes", GOLD, BORDER_GOLD, self.mostrar_alertas),
            ("REL", "Relatórios", "PDF/CSV profissional", BLUE, BORDER_BLUE, self.mostrar_relatorios),
            ("CAD", "Cadastrar", "Novo produto completo", GOLD, BORDER_GOLD, self.form_produto),
            ("BKP", "Backup", "Proteger banco de dados", BLUE, BORDER_BLUE, self.criar_backup),
            ("HIST", "Histórico", "Últimas movimentações", BLUE, BORDER_BLUE, self.mostrar_historico),
            ("AJD", "Ajuda", "Manual rápido", GOLD, BORDER_GOLD, self.mostrar_mais),
        ]:
            grid2.add_widget(self._tile(simb, titulo, sub, cor, borda, acao))
        cont.add_widget(grid2)

    def _kpi(self, simb, titulo, valor, rod, cor, borda, acao):
        hx = "1AA9FF" if cor == BLUE else "FF9A12"
        text = f"[color={hx}][size=16sp][b]{simb}[/b][/size][/color]\n[size=11sp]{titulo}[/size]\n[size=19sp][b]{valor}[/b][/size]\n[color={hx}][size=10sp]{rod}[/size][/color]"
        b = Botao(text=text, font_size="12sp", borda=borda)
        b.bind(on_release=lambda *_: self._safe(acao))
        return b

    def _tile(self, simb, titulo, sub, cor, borda, acao):
        hx = "1AA9FF" if cor == BLUE else "FF9A12"
        text = f"[color={hx}][size=16sp][b]{simb}[/b][/size][/color]\n[size=14sp][b]{titulo}[/b][/size]\n[size=10sp]{sub}[/size]\n[color={hx}][size=17sp][b]>[/b][/size][/color]"
        b = Botao(text=text, font_size="12sp", borda=borda)
        b.bind(on_release=lambda *_: self._safe(acao))
        return b

    def mostrar_acoes(self):
        self._clear()
        cont = self._scroll()
        cont.add_widget(self._card_titulo("Ações rápidas", "Rotinas essenciais sem travamento e com confirmação."))
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(500))
        for simb, titulo, sub, cor, borda, acao in [
            ("CAD", "Cadastrar produto", "Código, categoria e mínimo", BLUE, BORDER_BLUE, self.form_produto),
            ("ENT", "Entrada", "Produto recebido", BLUE, BORDER_BLUE, self.form_entrada),
            ("SAI", "Saída", "Consumo por turno", GOLD, BORDER_GOLD, self.form_saida),
            ("CONF", "Conferência", "Ajustar saldo físico", GOLD, BORDER_GOLD, self.form_conferencia),
            ("ALT", "Alertas", "Itens faltantes", GOLD, BORDER_GOLD, self.mostrar_alertas),
            ("BKP", "Backup", "Salvar dados", BLUE, BORDER_BLUE, self.criar_backup),
        ]:
            grid.add_widget(self._tile(simb, titulo, sub, cor, borda, acao))
        cont.add_widget(grid)

    def mostrar_estoque(self):
        self._clear()
        cont = self._scroll()
        cont.add_widget(self._card_titulo("Estoque atual", "Lista local salva no aparelho."))
        top = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(58))
        top.add_widget(self._tile("+", "Cadastrar", "novo item", BLUE, BORDER_BLUE, self.form_produto))
        top.add_widget(self._tile("CSV", "Exportar", "estoque", GOLD, BORDER_GOLD, self.exportar_estoque_csv))
        cont.add_widget(top)
        produtos = DB.produtos()
        if not produtos:
            cont.add_widget(Texto("Nenhum produto cadastrado ainda. Toque em Cadastrar.", "14sp", MUTED, True, "center", size_hint_y=None, height=dp(80)))
            return
        for p in produtos:
            q = float(p["quantidade"] or 0)
            baixo = q <= float(p["estoque_minimo"] or 0) and float(p["estoque_minimo"] or 0) > 0
            c = Card(orientation="vertical", size_hint_y=None, height=dp(82), padding=dp(9), borda=BORDER_GOLD if baixo else BORDER_BLUE)
            c.add_widget(Texto(f"[b]{p['codigo']} • {p['nome']}[/b]", "13sp", WHITE, True))
            c.add_widget(Texto(f"Saldo: [b]{qtd_fmt(q)} {p['unidade']}[/b]  | Mínimo: {qtd_fmt(float(p['estoque_minimo'] or 0))} | {p['categoria']} | {p['localizacao']}", "11sp", GOLD if baixo else MUTED))
            cont.add_widget(c)

    def _popup_form(self, titulo: str, campos: List[Tuple[str, str]], salvar_callback):
        box = BoxLayout(orientation="vertical", spacing=dp(7), padding=dp(9))
        scroll = ScrollView(do_scroll_x=False)
        form = BoxLayout(orientation="vertical", spacing=dp(7), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))
        inputs: Dict[str, Campo] = {}
        for chave, hint in campos:
            form.add_widget(Texto(hint, "11sp", MUTED, True, size_hint_y=None, height=dp(20)))
            inp = Campo(hint)
            inp.size_hint_y = None
            inp.height = dp(46)
            inputs[chave] = inp
            form.add_widget(inp)
        scroll.add_widget(form)
        box.add_widget(scroll)
        botoes = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(7))
        cancelar = Botao(text="[b]CANCELAR[/b]", borda=BORDER_DIM)
        salvar = Botao(text="[b]SALVAR[/b]", borda=BORDER_GOLD)
        botoes.add_widget(cancelar)
        botoes.add_widget(salvar)
        box.add_widget(botoes)
        pop = Popup(title=titulo, content=box, size_hint=(0.94, 0.86), separator_color=GOLD)
        cancelar.bind(on_release=pop.dismiss)

        def _salvar(*_):
            dados = {k: v.text.strip() for k, v in inputs.items()}
            try:
                salvar_callback(dados)
                pop.dismiss()
            except Exception as e:
                self.msg(str(e), erro=True)
        salvar.bind(on_release=_salvar)
        pop.open()

    def form_produto(self):
        campos = [
            ("codigo", "Código do produto *"),
            ("nome", "Nome do produto *"),
            ("categoria", "Categoria: CONGELADO, RESFRIADO, NÃO PERECÍVEL..."),
            ("unidade", "Unidade: KG, UN, CX, L..."),
            ("estoque_minimo", "Estoque mínimo"),
            ("custo_unitario", "Custo unitário"),
            ("localizacao", "Localização"),
            ("observacao", "Observação"),
        ]
        def salvar(d):
            if not d.get("codigo") or not d.get("nome"):
                raise ValueError("Código e nome são obrigatórios.")
            d["categoria"] = d.get("categoria") or "OUTROS"
            d["unidade"] = d.get("unidade") or "UN"
            DB.cadastrar_produto(d)
            self.msg("Produto cadastrado com sucesso.")
            self.mostrar_estoque()
        self._popup_form("Cadastrar Produto", campos, salvar)

    def _form_mov(self, tipo: str):
        campos = [
            ("produto", "Código ou parte do nome do produto *"),
            ("quantidade", "Quantidade *"),
            ("data_consumo", "Data consumo/utilização (dd/mm/aaaa)"),
            ("turno", "Turno A=Almoço, B=Janta, C=Ceia"),
            ("observacao", "Observação"),
        ]
        def salvar(d):
            prod = DB.produto_por_codigo_ou_nome(d.get("produto", ""))
            if not prod:
                raise ValueError("Produto não encontrado. Cadastre primeiro ou confira o nome/código.")
            qtd = normalizar_numero(d.get("quantidade", "0"))
            if qtd <= 0:
                raise ValueError("Quantidade precisa ser maior que zero.")
            turno = d.get("turno", "").strip().upper()
            if tipo == "SAIDA" and turno and turno not in TURNOS:
                raise ValueError("Turno inválido. Use A, B ou C.")
            antes, depois = DB.movimentar(int(prod["id"]), tipo, qtd, d.get("data_consumo", ""), turno, d.get("observacao", ""))
            self.msg(f"{tipo} salva. Antes: {qtd_fmt(antes)} | Atual: {qtd_fmt(depois)} {prod['unidade']}.")
            self.mostrar_painel()
        self._popup_form("Nova Entrada" if tipo == "ENTRADA" else "Nova Saída", campos, salvar)

    def form_entrada(self):
        self._form_mov("ENTRADA")

    def form_saida(self):
        self._form_mov("SAIDA")

    def form_conferencia(self):
        campos = [
            ("produto", "Código ou parte do nome do produto *"),
            ("quantidade", "Quantidade física encontrada *"),
            ("observacao", "Observação da conferência"),
        ]
        def salvar(d):
            prod = DB.produto_por_codigo_ou_nome(d.get("produto", ""))
            if not prod:
                raise ValueError("Produto não encontrado.")
            fisico = normalizar_numero(d.get("quantidade", "0"))
            atual = float(prod["quantidade"] or 0)
            diff = fisico - atual
            if abs(diff) < 0.0001:
                self.msg("Conferência OK. Não houve diferença.")
                return
            DB.movimentar(int(prod["id"]), "ENTRADA" if diff > 0 else "SAIDA", abs(diff), data_br(), "", "AJUSTE DE CONFERÊNCIA - " + d.get("observacao", ""))
            self.msg(f"Conferência ajustada. Diferença: {qtd_fmt(diff)} {prod['unidade']}.")
            self.mostrar_estoque()
        self._popup_form("Conferência de Estoque", campos, salvar)

    def mostrar_alertas(self):
        self._clear()
        cont = self._scroll()
        cont.add_widget(self._card_titulo("Alertas operacionais", "Itens abaixo do mínimo e risco de falta."))
        baixos = DB.estoque_baixo()
        if not baixos:
            cont.add_widget(Texto("[color=0AE066][b]Nenhum item crítico no momento.[/b][/color]", "16sp", GREEN, True, "center", size_hint_y=None, height=dp(110)))
            return
        for r in baixos:
            falta = max(0.0, float(r["estoque_minimo"] or 0) - float(r["quantidade"] or 0))
            c = Card(orientation="vertical", size_hint_y=None, height=dp(92), padding=dp(9), borda=BORDER_GOLD)
            c.add_widget(Texto(f"[b]{r['nome']}[/b]", "14sp", WHITE, True))
            c.add_widget(Texto(f"Atual: {qtd_fmt(float(r['quantidade']))} {r['unidade']} | Mínimo: {qtd_fmt(float(r['estoque_minimo']))} | Falta sugerida: {qtd_fmt(falta)}", "12sp", GOLD, True))
            c.add_widget(Texto(f"Local: {r['localizacao']}", "11sp", MUTED))
            cont.add_widget(c)

    def mostrar_historico(self):
        self._clear()
        cont = self._scroll()
        cont.add_widget(self._card_titulo("Histórico", "Últimas movimentações registradas."))
        rows = DB.ultimas_mov()
        if not rows:
            cont.add_widget(Texto("Ainda não existem movimentações.", "14sp", MUTED, True, "center", size_hint_y=None, height=dp(90)))
            return
        for m in rows:
            borda = BORDER_BLUE if m["tipo"] == "ENTRADA" else BORDER_GOLD
            c = Card(orientation="vertical", size_hint_y=None, height=dp(88), padding=dp(9), borda=borda)
            sinal = "+" if m["tipo"] == "ENTRADA" else "-"
            c.add_widget(Texto(f"[b]{m['tipo']}[/b] • {m['nome']}", "13sp", WHITE, True))
            c.add_widget(Texto(f"{sinal}{qtd_fmt(float(m['quantidade']))} {m['unidade']} | Depois: {qtd_fmt(float(m['estoque_depois']))} | {m['data_movimento']} | Turno {m['turno'] or '-'}", "11sp", GOLD if m["tipo"] == "SAIDA" else BLUE))
            c.add_widget(Texto(m["observacao"] or "Sem observação", "10sp", MUTED))
            cont.add_widget(c)

    def mostrar_relatorios(self):
        self._clear()
        cont = self._scroll()
        cont.add_widget(self._card_titulo("Relatórios", "Arquivos profissionais salvos no aparelho."))
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(230))
        grid.add_widget(self._tile("PDF", "Estoque PDF", "visual premium", GOLD, BORDER_GOLD, self.gerar_pdf_estoque))
        grid.add_widget(self._tile("CSV", "Estoque CSV", "planilha", BLUE, BORDER_BLUE, self.exportar_estoque_csv))
        grid.add_widget(self._tile("MOV", "Histórico CSV", "movimentações", BLUE, BORDER_BLUE, self.exportar_mov_csv))
        grid.add_widget(self._tile("BKP", "Backup", "banco completo", GOLD, BORDER_GOLD, self.criar_backup))
        cont.add_widget(grid)
        cont.add_widget(Texto(f"Pasta de saída:\n{REPORT_DIR}", "12sp", MUTED, False, "center", size_hint_y=None, height=dp(90)))

    def mostrar_mais(self):
        self._clear()
        cont = self._scroll()
        cont.add_widget(self._card_titulo("Ajuda e informações", "Uso rápido do sistema."))
        textos = [
            "1. Cadastre o produto com código, unidade, estoque mínimo e custo.",
            "2. Use Entrada quando o item chegar na unidade.",
            "3. Use Saída para baixar consumo e informe o turno A, B ou C.",
            "4. Alertas mostram itens abaixo do mínimo.",
            "5. Relatórios e backups ficam salvos no armazenamento interno do aplicativo.",
            "6. O banco é local, leve e estável para Samsung A06.",
        ]
        for t in textos:
            c = Card(size_hint_y=None, height=dp(64), padding=dp(10), borda=BORDER_DIM)
            c.add_widget(Texto(t, "13sp", WHITE))
            cont.add_widget(c)

    def exportar_estoque_csv(self):
        caminho = REPORT_DIR / f"estoque_express_{stamp()}.csv"
        rows = DB.produtos()
        with caminho.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Código", "Produto", "Categoria", "Unidade", "Quantidade", "Mínimo", "Custo", "Local", "Observação"])
            for p in rows:
                w.writerow([p["codigo"], p["nome"], p["categoria"], p["unidade"], qtd_fmt(float(p["quantidade"] or 0)), qtd_fmt(float(p["estoque_minimo"] or 0)), moeda(float(p["custo_unitario"] or 0)), p["localizacao"], p["observacao"]])
        self.msg(f"CSV criado com sucesso:\n{caminho}")

    def exportar_mov_csv(self):
        caminho = REPORT_DIR / f"movimentacoes_express_{stamp()}.csv"
        rows = DB.ultimas_mov(10000)
        with caminho.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Data", "Tipo", "Código", "Produto", "Quantidade", "Unidade", "Data Consumo", "Turno", "Antes", "Depois", "Observação"])
            for m in rows:
                w.writerow([m["data_movimento"], m["tipo"], m["codigo"], m["nome"], qtd_fmt(float(m["quantidade"])), m["unidade"], m["data_consumo"], m["turno"], qtd_fmt(float(m["estoque_antes"])), qtd_fmt(float(m["estoque_depois"])), m["observacao"]])
        self.msg(f"CSV criado com sucesso:\n{caminho}")

    def criar_backup(self):
        caminho = BACKUP_DIR / f"backup_express_{stamp()}.db"
        src = sqlite3.connect(str(DB_PATH))
        dst = sqlite3.connect(str(caminho))
        with dst:
            src.backup(dst)
        src.close(); dst.close()
        self.msg(f"Backup criado com sucesso:\n{caminho}")

    def gerar_pdf_estoque(self):
        caminho = REPORT_DIR / f"relatorio_estoque_express_{stamp()}.pdf"
        rows = DB.produtos()
        linhas = ["RELATÓRIO DE ESTOQUE - EXPRESS COLORADO", f"{data_br()} - By Maicon", ""]
        for p in rows:
            linhas.append(f"{p['codigo']} | {p['nome']} | {qtd_fmt(float(p['quantidade'] or 0))} {p['unidade']} | Mínimo {qtd_fmt(float(p['estoque_minimo'] or 0))} | {p['categoria']}")
        if not rows:
            linhas.append("Nenhum produto cadastrado.")
        self._pdf_simples(caminho, linhas)
        self.msg(f"PDF criado com sucesso:\n{caminho}")

    def _pdf_simples(self, path: Path, linhas: List[str]):
        # Gerador PDF mínimo e válido, sem depender de bibliotecas pesadas no Android.
        def esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        y = 800
        stream_lines = ["BT", "/F1 18 Tf", "50 800 Td", f"({esc(linhas[0] if linhas else 'RELATÓRIO')}) Tj", "/F1 10 Tf"]
        stream_lines.append("0 -24 Td")
        for linha in linhas[1:55]:
            stream_lines.append(f"({esc(linha[:105])}) Tj")
            stream_lines.append("0 -14 Td")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", "replace")
        objs = []
        objs.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
        objs.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
        objs.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n")
        objs.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj\n")
        objs.append(b"5 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n")
        out = [b"%PDF-1.4\n"]
        offsets = [0]
        pos = len(out[0])
        for o in objs:
            offsets.append(pos)
            out.append(o)
            pos += len(o)
        xref_pos = pos
        xref = [f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()]
        for off in offsets[1:]:
            xref.append(f"{off:010d} 00000 n \n".encode())
        trailer = f"trailer << /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
        path.write_bytes(b"".join(out + xref + [trailer]))


class SistemaExpressApp(App):
    title = APP_TITLE
    icon = "icon.png"

    def build(self):
        return SistemaTela()


if __name__ == "__main__":
    SistemaExpressApp().run()
